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

import btree
import json

d = dht.DHT22(machine.Pin(25))
CLIENT_ID = ubinascii.hexlify(machine.unique_id()).decode('utf-8')
periodo = 20
modo = True

def sub_cb(topic, msg, retained):
    print('Topic = {} -> Valor = {}'.format(topic.decode(), msg.decode()))

async def wifi_han(state):
    print('Wifi is ', 'up' if state else 'down')
    await asyncio.sleep(1)

# If you connect with clean_session True, must re-subscribe (MQTT spec 3.1.2.4)
async def conn_han(client):
    await client.subscribe('alan/'+CLIENT_ID+'/temperatura', 1)
    await client.subscribe('alan/'+CLIENT_ID+'/humedad', 1)
    await client.subscribe('alan/'+CLIENT_ID+'/setpoint', 1)
    await client.subscribe('alan/'+CLIENT_ID+'/periodo', 1)
    await client.subscribe('alan/'+CLIENT_ID+'/modo', 1)
    await client.subscribe('alan/'+CLIENT_ID+'/rele', 1)

async def main(client):
    await client.connect()
    n = 0
    await asyncio.sleep(2)  # Give broker time
    while True:
        try:
            d.measure()
            try:
                temperatura=d.temperature()
                await client.publish('alan/'+CLIENT_ID+'/temperatura', '{}'.format(temperatura), qos = 1)
            except OSError as e:
                print("sin sensor temperatura")
            try:
                humedad=d.humidity()
                await client.publish('alan/'+CLIENT_ID+'/humedad', '{}'.format(humedad), qos = 1)
            except OSError as e:
                print("sin sensor humedad")  
        except OSError as e:
            print("sin sensor")
        try:
            await client.publish('alan/'+CLIENT_ID+'/periodo', '{}'.format(periodo), qos = 1)
        except:
            print("No se definio periodo")
        await asyncio.sleep(periodo)  # Broker is slow

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