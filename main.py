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
import dht, machine
import ubinascii
from time import sleep

import btree
import json

d = dht.DHT22(machine.Pin(25))
CLIENT_ID = ubinascii.hexlify(machine.unique_id()).decode('utf-8')
rele = "apagado"
flagRele = 1
destello = 0
led = machine.Pin(2, machine.Pin.OUT)
accionrele = machine.Pin(13, machine.Pin.OUT)
led.value(0)
datos = {
    'temperatura': 0.0,
    'humedad': 0.0,
    'setpoint': 25.5,
    'periodo': 3,
    'modo': "manual"
    }
def sub_cb(topic, msg, retained):
    global destello
    global rele
    global flagRele
    topico = topic.decode()
    mensaje = msg.decode()

    print('Topic = {} -> Valor = {}'.format(topico, mensaje))

    if topico == 'alan/setpoint':
        datos['setpoint']=float(mensaje)

    elif topico == 'alan/periodo':
        datos['periodo']=int(mensaje)

    elif topico == 'alan/modo':
        datos['modo']=mensaje.lower()
        if datos['modo'] == 'manual':
            flagRele = 1
        if datos['modo'] == 'automatico':
            flagRele = 0
    
    elif topico == 'alan/rele':
        rele = mensaje.lower()
    
    elif topico == 'alan/destello':
        destello = int(mensaje)




    

async def wifi_han(state):
    print('Wifi is ', 'up' if state else 'down')
    await asyncio.sleep(1)

# If you connect with clean_session True, must re-subscribe (MQTT spec 3.1.2.4)
async def conn_han(client):
    await client.subscribe('alan/setpoint', 1)
    await client.subscribe('alan/periodo', 1)
    await client.subscribe('alan/destello', 1)
    await client.subscribe('alan/modo', 1)
    await client.subscribe('alan/rele', 1)
    await client.subscribe('alan/'+CLIENT_ID, 1)

async def main(client):
    global destello
    global rele
    global flagRele
    await client.connect()
    n = 0
    await asyncio.sleep(2)  # Give broker time
    while True:
        try:
            d.measure()
            try:
                datos['humedad']=d.humidity()
                datos['temperatura']=d.temperature()
                await client.publish('alan/'+CLIENT_ID, json.dumps(datos), qos=1)
            except OSError as e:
                print("Error al publicar datos:", e)
        except OSError as e:
            print("Error al medir los datos")
        try:
            if flagRele == 1:
                if rele == 'encendido':
                    accionrele.value(0)
                    print("Rele encendido manualmente")
                elif rele == 'apagado':
                    accionrele.value(1)
                    print("Rele apagado manualmente")
            else:
                if datos['temperatura']>datos['setpoint']:
                    accionrele.value(0)
                    print("Rele encendido automatico")
                if datos['temperatura']<=datos['setpoint']:
                    accionrele.value(1)
                    print("Rele apagado automatico")
        except OSError as e:
            print("Rele NO Funciona")
        try:
            if destello == 1:
                print("Destello")
                led.value(not led.value())
                sleep(2)
                led.value(not led.value())
                destello = 0
        except OSError as e:
            print("Destello NO Funciona")
        await asyncio.sleep(datos['periodo'])  # Broker is slow



# Define configuration
config['subs_cb'] = sub_cb
config['connect_coro'] = conn_han
config['wifi_coro'] = wifi_han
config['ssl'] = True

# Set up client
MQTTClient.DEBUG = True  # Optional
client = MQTTClient(config)
try:
    asyncio.run(main(client))
finally:
    client.close()
    asyncio.new_event_loop()
