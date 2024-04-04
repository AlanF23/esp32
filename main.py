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
import ujson

d = dht.DHT22(machine.Pin(25))
CLIENT_ID = ubinascii.hexlify(machine.unique_id()).decode('utf-8')
periodo = 3
rele = "apagado"
setpoint = 26
modo = "manual"

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
    db[key] = ujson.dumps(value)

# Función para recuperar datos de la base de datos
def retrieve_data(db, key):
    if key in db:
        return ujson.loads(db[key])
    else:
        return None

# Inicializar la base de datos
db = init_db()

def sub_cb(topic, msg, retained):
    print('Topic = {} -> Valor = {}'.format(topic.decode(), msg.decode()))

async def wifi_han(state):
    print('Wifi is ', 'up' if state else 'down')
    await asyncio.sleep(1)

# If you connect with clean_session True, must re-subscribe (MQTT spec 3.1.2.4)
async def conn_han(client):
    await client.subscribe('setpoint', 1)
    await client.subscribe('periodo', 1)
    await client.subscribe('destello', 1)
    await client.subscribe('modo', 1)
    await client.subscribe('rele', 1)

async def main(client):
    await client.connect()
    n = 0
    await asyncio.sleep(2)  # Give broker time
    while True:
        try:
            d.measure()
            datos = {
                'temperatura': d.temperature(),
                'humedad': d.humidity(),
                'setpoint': setpoint,
                'periodo': periodo,
                'modo': modo
            }
            try:
                await client.publish('alan/'+CLIENT_ID, ujson.dumps(datos), qos=1)
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
            # Almacenar el diccionario completo en la base de datos
            store_data(db, 'parametros', parametros)
        except OSError as e:
            print("Error al guardar los parametros")
        try:
            if modo == "automatico":
                if datos['temperatura'] > setpoint:
                    rele = "encendido"
                    #codigo que active el pin del relé
                else:
                    rele = "apagado"
            if modo == "manual":
                # y aca ya no sé xd
                pass
        except OSError as e:
            print("El relé no funciona")
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
