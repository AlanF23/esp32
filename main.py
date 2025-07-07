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
import machine,  onewire, ds18x20, json
from collections import OrderedDict

# Configuración del pin de datos del DS18B20
ow = onewire.OneWire(machine.Pin(5))
ds = ds18x20.DS18X20(ow)
roms = ds.scan()

# Sensor de turbidez en GPIO34
adc = machine.ADC(machine.Pin(34))
adc.atten(machine.ADC.ATTN_11DB)  # Rango 0–3.6V
adc.width(machine.ADC.WIDTH_12BIT)  # Resolución 0–4095


def sub_cb(topic, msg, retained):
    print('Topic = {} -> Valor = {}'.format(topic.decode(), msg.decode()))

async def wifi_han(state):
    print('Wifi is ', 'up' if state else 'down')
    await asyncio.sleep(1)

# If you connect with clean_session True, must re-subscribe (MQTT spec 3.1.2.4)
async def conn_han(client):
    await client.subscribe('prueba/temperatura', 1)
    await client.subscribe('prueba/turbidez', 1)
    await client.subscribe('prueba/datos', 1)

async def main(client):
    await client.connect()
    await asyncio.sleep(2)  # Give broker time
    while True:
        try:
            ds.convert_temp()
            await asyncio.sleep(1)  # Wait for conversion
            for rom in roms:
                temp = ds.read_temp(rom)
                if temp is not None:
                    await client.publish('prueba/temperatura', '{}'.format(temp), qos=1)
                else:
                    print("Error al leer temperatura")

            # Leer turbidez
            turb_raw = adc.read()
            voltaje = turb_raw * (3.3 / 4095)  # Convertir a voltios
            voltaje_real = voltaje * 1.5  # Ajuste del voltaje
            ntu = -1120.4 * voltaje_real**2 + 5742.3 * voltaje_real - 4352.9
            ntu = max(0, round(ntu, 2))  # Limitar a 0 si da negativo, redondear
            print("Voltaje: ", voltaje)
            await client.publish('prueba/turbidez', str(ntu), qos=1)
            datos=json.dumps(OrderedDict([
                ('temperatura',temp),
                ('turbidez',ntu)
            ]))
            await client.publish('prueba/datos', datos, qos = 1)
        except Exception as e:
            print("Error al leer los sensores:", e)
        await asyncio.sleep(5)  # Broker is slow

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
