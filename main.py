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
import machine

# Sensor de turbidez en GPIO4
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
    await client.subscribe('prueba/turbidez', 1)

async def main(client):
    await client.connect()
    await asyncio.sleep(2)  # Give broker time
    while True:
        await asyncio.sleep(0.05)

        try:
            turb_raw = adc.read()
            print("RAW:", turb_raw)
        except Exception as e:
            print("Error en lectura ADC:", e)

        try:
            voltaje = turb_raw * (3.3 / 4095)
            ntu = -1120.4 * voltaje**2 + 5742.3 * voltaje - 4352.9
            ntu = max(0, round(ntu, 2))
            print("NTU:", ntu)
        except Exception as e:
            print("Error en cálculo:", e)

        try:
            await client.publish('prueba/turbidez', str(ntu), qos=1)
        except Exception as e:
            print("Error al publicar MQTT:", e)

        await asyncio.sleep(5)

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
