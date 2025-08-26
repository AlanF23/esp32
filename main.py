# (C) Copyright Peter Hinch 2017-2019.
# Released under the MIT licence.

# This demo publishes to topic "result" and also subscribes to that topic.
# This demonstrates bidirectional TLS communication.
# You can also run the following on a PC to verify:
# mosquitto_sub -h test.mosquitto.org -t result
# To get mosquitto_sub to use a secure connection use this, offered by @gmrza:
# mosquitto_sub -h <my local mosquitto server> -t result -u <username> -P <password> -p 8883

# Public brokers https://github.com/mqtt/mqtt.github.io/wiki/public_brokers

# red LED: ON == WiFi fail
# green LED heartbeat: demonstrates scheduler is running.

from mqtt_as import MQTTClient
from mqtt_local import config
import uasyncio as asyncio
import machine,  onewire, ds18x20, json, ubinascii
from collections import OrderedDict
import time

# Configuración del pin de datos del DS18B20
ow = onewire.OneWire(machine.Pin(5))
ds = ds18x20.DS18X20(ow)
roms = ds.scan()
CLIENT_ID = ubinascii.hexlify(machine.unique_id()).decode('utf-8')

# Sensor de turbidez en GPIO34
adc = machine.ADC(machine.Pin(34))
adc.atten(machine.ADC.ATTN_11DB)  # Rango 0–3.6V
adc.width(machine.ADC.WIDTH_12BIT)  # Resolución 0–4095

calentador = "apagado"
flagcalentador = 1
accioncalentador = machine.Pin(21, machine.Pin.OUT)

ventilador = "apagado"
flagventilador = 1
accionventilador = machine.Pin(22, machine.Pin.OUT)

filtro = "apagado"
flagfiltro = 1
accionfiltro = machine.Pin(23, machine.Pin.OUT)

alimentar = 0
# Pines del motor paso a paso (ULN2003 o similar)
IN1 = machine.Pin(25, machine.Pin.OUT)  # Cambiar a los pines que uses
IN2 = machine.Pin(26, machine.Pin.OUT)
IN3 = machine.Pin(32, machine.Pin.OUT)
IN4 = machine.Pin(33, machine.Pin.OUT)

estado = 0
datos = {
    'temperatura': 0.0,
    'turbidez': 0.0,
    'setpointtemperatura': 25.0,
    'setpointturbidez': 2800.0,
    'periodo': 5,
    'modo': "manual"
    }
estados = {
    'calentador': 0,
    'ventilador': 0,
    'filtro': 0
}
def sub_cb(topic, msg, retained):
    global alimentar, estado
    global calentador, flagcalentador
    global ventilador, flagventilador
    global filtro, flagfiltro
    topico = topic.decode()
    mensaje = msg.decode()
    print('Topic = {} -> Valor = {}'.format(topico, mensaje))
    if topico == 'setpointtemperatura':
        datos['setpointtemperatura']=float(mensaje)

    elif topico == 'setpointturbidez':
        datos['setpointturbidez']=float(mensaje)

    elif topico == 'periodo':
        datos['periodo']=int(mensaje)

    elif topico == 'modo':
        datos['modo']=mensaje.lower()
        if datos['modo'] == 'manual':
            flagventilador = 1
            flagcalentador = 1
            flagfiltro = 1
        if datos['modo'] == 'auto':
            flagventilador = 0
            flagcalentador = 0
            flagfiltro = 0
    
    elif topico == 'ventilador':
        ventilador = mensaje.lower()
    elif topico == 'calentador':
        calentador = mensaje.lower()
    elif topico == 'filtro':
        filtro = mensaje.lower()

    elif topico == 'alimentar':
        alimentar = int(mensaje)
    elif topico == 'estado':
        estado = int(mensaje)

async def wifi_han(state):
    print('Wifi is ', 'up' if state else 'down')
    await asyncio.sleep(1)

# If you connect with clean_session True, must re-subscribe (MQTT spec 3.1.2.4)
async def conn_han(client):
    await client.subscribe('prueba/'+CLIENT_ID, 1)
    await client.subscribe('setpointtemperatura', 1)
    await client.subscribe('setpointturbidez', 1)
    await client.subscribe('periodo', 1)
    await client.subscribe('modo', 1)
    await client.subscribe('ventilador', 1)
    await client.subscribe('calentador', 1)
    await client.subscribe('filtro', 1)
    await client.subscribe('alimentar', 1)
    await client.subscribe('estado', 1)


# Secuencia del motor (paso completo)
pasos = [
    [1, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 1],
    [1, 0, 0, 1]
]

def mover_motor(pasos_a_mover=50, delay_ms=2):
    """Gira el motor cierta cantidad de pasos."""
    for _ in range(pasos_a_mover):
        for paso in pasos:
            IN1.value(paso[0])
            IN2.value(paso[1])
            IN3.value(paso[2])
            IN4.value(paso[3])
            time.sleep_ms(delay_ms)
    # Apagar bobinas para evitar consumo innecesario
    IN1.value(0)
    IN2.value(0)
    IN3.value(0)
    IN4.value(0)

# Variables para control de alimentación automática
ultima_fecha_alimentacion = None

def alimentar_si_corresponde():
    """Alimenta automáticamente a las 20:00 si está en modo automático."""
    global ultima_fecha_alimentacion
    if datos['modo'] == 'auto':
        ahora = time.time()  # (año, mes, día, hora, minuto, segundo, día_sem, día_año)
        tiempo_local = time.localtime(ahora)
        hora, minuto = tiempo_local[3], tiempo_local[4]
        fecha_hoy = (tiempo_local[0], tiempo_local[1], tiempo_local[2])  # Año, mes, día
        if hora == 21 and 24 <= minuto <= 26:
            if ultima_fecha_alimentacion != fecha_hoy:
                print("Alimentación automática")
                mover_motor()
                ultima_fecha_alimentacion = fecha_hoy

def alimentar_manual():
    """Alimenta si el comando MQTT lo solicita."""
    global alimentar
    if datos['modo'] == 'manual' and alimentar == 1:
        print("Alimentación manual")
        mover_motor()
        alimentar = 0



async def main(client):
    global estado
    await client.connect()
    await asyncio.sleep(2)  # Give broker time
    while True:
        try:
            ds.convert_temp()
            await asyncio.sleep(1)  # Wait for conversion
            for rom in roms:
                temp = ds.read_temp(rom)

            # Leer turbidez
            turb_raw = adc.read()
            voltaje = turb_raw * (3.3 / 4095)  # Convertir a voltios
            voltaje_real = voltaje * 1.5  # Ajuste del voltaje
            ntu = -1120.4 * voltaje_real**2 + 5742.3 * voltaje_real - 4352.9
            ntu = max(0, round(ntu, 2))  # Limitar a 0 si da negativo, redondear
            #print("Voltaje: ", voltaje)
            try:
                datos['temperatura']=temp
                datos['turbidez']=ntu
                await client.publish('prueba/'+CLIENT_ID, json.dumps(datos), qos = 1)
            except Exception as e:
                print("Error al publicar datos:", e)
        except Exception as e:
            print("Error al leer los sensores:", e)
        try:
            if flagventilador == 1:
                if ventilador == 'encendido':
                    accionventilador.value(1)
                    print("Ventilador encendido manualmente")
                elif ventilador == 'apagado':
                    accionventilador.value(0)
                    print("Ventilador apagado manualmente")
            else:
                if datos['temperatura'] > (datos['setpointtemperatura']+1.0):
                    accionventilador.value(1)
                else:
                    accionventilador.value(0)
        except OSError as e:
            print("Ventilador NO Funciona")
        try:
            if flagcalentador == 1:
                if calentador == 'encendido':
                    accioncalentador.value(1)
                    print("Calentador encendido manualmente")
                elif calentador == 'apagado':
                    accioncalentador.value(0)
                    print("Calentador apagado manualmente")
            else:
                if datos['temperatura'] < (datos['setpointtemperatura']-1.0):
                    accioncalentador.value(1)
                else:
                    accioncalentador.value(0)
        except OSError as e:
            print("Calentador NO Funciona")
        try:
            if flagfiltro == 1:
                if filtro == 'encendido':
                    accionfiltro.value(1)
                    print("Filtro encendido manualmente")
                elif filtro == 'apagado':
                    accionfiltro.value(0)
                    print("Filtro apagado manualmente")
            else:
                if datos['turbidez'] > datos['setpointturbidez']:
                    accionfiltro.value(1)
                else:
                    accionfiltro.value(0)
        except OSError as e:
            print("Filtro NO Funciona")
        try:
            if estado == 1:
                estados['calentador'] = accioncalentador.value()
                estados['ventilador'] = accionventilador.value()
                estados['filtro'] = accionfiltro.value()
                await client.publish('estados/'+CLIENT_ID, json.dumps(estados), qos = 1)
                estado = 0
        except OSError as e:
            print("Estado NO Funciona")
        try:
            alimentar_manual()
            alimentar_si_corresponde()
        except OSError as e:
            print("Alimentador NO Funciona")
        await asyncio.sleep(datos['periodo'])  # Broker is slow

# Define configuration
config['subs_cb'] = sub_cb
config['connect_coro'] = conn_han
config['wifi_coro'] = wifi_han
config['ssl'] = False

# Set up client
MQTTClient.DEBUG = True  # Optional
client = MQTTClient(config)
try:
    asyncio.run(main(client))
finally:
    client.close()
    asyncio.new_event_loop()
