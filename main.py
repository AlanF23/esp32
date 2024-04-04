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
rele = "apagado"
setpoint = 26
modo = "manual"

def sub_cb(topic, msg, retained):
    print('Topic = {} -> Valor = {}'.format(topic.decode(), msg.decode()))

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
'''
# Función para inicializar la base de datos
def init_db():
    try:
        with open('config.db', 'r+b') as f:
            return btree.open(f)
    except OSError:
        with open('config.db', 'w+b') as f:
            return btree.open(f)

# Función para almacenar datos en la base de datos
def store_data(db, key, value):
    try:
        db[key] = json.dumps(value)
    except Exception as e:
        print("Error al almacenar datos:", e)

# Función para recuperar datos de la base de datos
def retrieve_data(db, key):
    if key in db:
        return json.loads(db[key])
    else:
        return None
'''

async def main(client):
    await client.connect()
    n = 0
    await asyncio.sleep(2)  # Give broker time
    while True:
        f = open("config.txt", "w+b")
        # Now open a database itself
        db = btree.open(f)
        try:
            d.measure()
            try:
                datos = {
                'temperatura': d.temperature(),
                'humedad': d.humidity(),
                'setpoint': setpoint,
                'periodo': periodo,
                'modo': modo
                }
                await client.publish('alan/'+CLIENT_ID, json.dumps(datos), qos=1)
            except OSError as e:
                print("Error al publicar datos:", e)
        except OSError as e:
            print("Error al medir los datos")
        try:
            parametros = {
                'setpoint': setpoint,
                'periodo': periodo,
                'modo': modo,
                'rele': rele
            }
            db[b'datos'] = b'parametros'
        except OSError as e:
            print("Error al guardar los parametros")
        '''try:
            if modo == "automatico":
                if datos['temperatura'] > setpoint:
                    rele = "encendido"
                    #codigo que active el pin del relé
                else:
                    rele = "apagado"
            if modo == "manual":
                # y aca ya no sé xd
                pass
        except:
            print("El relé no funciona")'''
        db.close()
        f.close()
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
