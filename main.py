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
led = machine.Pin(2, machine.Pin.OUT)
led.value(0)
estado_led = ""
datos = {
    'temperatura': 0.0,
    'humedad': 0.0,
    }

def sub_cb(topic, msg, retained):
    global estado_led
    topico = topic.decode()
    mensaje = msg.decode()

    print('Topic = {} -> Valor = {}'.format(topico, mensaje))
    if topico == '/switch_led/':
        estado_led = mensaje
        print("Estado del led en sub_cb: {}".format(mensaje))


async def wifi_han(state):
    print('Wifi is ', 'up' if state else 'down')
    await asyncio.sleep(1)

# If you connect with clean_session True, must re-subscribe (MQTT spec 3.1.2.4)
async def conn_han(client):
    await client.subscribe('/switch_led/', 1)
    await client.subscribe('/sensores_remotos/#', 1)

async def manejo_led():
    global estado_led
    await asyncio.sleep(4)
    while True:
        try:
            if estado_led == "true":
                led.value(1)
                await client.publish('/estado', str(led.value()), qos=1)
            if estado_led == "false":
                led.value(0)
                await client.publish('/estado', str(led.value()), qos=1)
        except OSError as e:
            print("No funciona el cambio del led")
        await asyncio.sleep(0.5)

async def main(client):
    global estado_led
    await client.connect()
    n = 0
    await asyncio.sleep(2)  # Give broker time
    while True:
        try:
            d.measure()
            try:
                datos['humedad']=d.humidity()
                datos['temperatura']=d.temperature()
                await client.publish('/sensores_remotos/', json.dumps(datos), qos=1)
            except OSError as e:
                print("Error al publicar datos:", e)
        except OSError as e:
            print("Error al medir los datos")
        await asyncio.sleep(5)  # Broker is slow

async def task(client):
    await asyncio.gather(main(client), manejo_led())


# Define configuration
config['subs_cb'] = sub_cb
config['connect_coro'] = conn_han
config['wifi_coro'] = wifi_han
config['ssl'] = True

# Set up client
MQTTClient.DEBUG = True  # Optional
client = MQTTClient(config)
try:
    asyncio.run(task(client))
finally:
    client.close()
    asyncio.new_event_loop()
