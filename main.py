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

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from mqtt_as import MQTTClient
from mqtt_local import config
import logging, os, aiomysql, traceback, locale
import uasyncio as asyncio
import dht, machine
import ubinascii
from time import sleep
import json
import matplotlib.pyplot as plt
from io import BytesIO

token=os.environ["TB_TOKEN"]

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
    'periodo': 10,
    'modo': "manual"
    }

#ACA EMPIEZA LO COPIADO DEL EJEMPLO DEL BOT
logging.basicConfig(format='%(asctime)s - TelegramBot - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("se conectó: " + str(update.message.from_user.id))
    if update.message.from_user.first_name:
        nombre=update.message.from_user.first_name
    else:
        nombre=""
    if update.message.from_user.last_name:
        apellido=update.message.from_user.last_name
    else:
        apellido=""
    kb = [["temperatura"],["humedad"],["gráfico temperatura"],["gráfico humedad"]]
    await context.bot.send_message(update.message.chat.id, text="Bienvenido al Bot "+ nombre + " " + apellido,reply_markup=ReplyKeyboardMarkup(kb))

async def acercade(update: Update, context):
    await context.bot.send_message(update.message.chat.id, text="Este bot fue creado para el curso de IoT FIO")

async def kill(update: Update, context):
    logging.info(context.args)
    if context.args and context.args[0] == '@e':
        await context.bot.send_animation(update.message.chat.id, "CgACAgEAAxkBAANXZAiWvDIEfGNVzodgTgH1o5z3_WEAAmUCAALrx0lEZ8ytatzE5X0uBA")
        await asyncio.sleep(6)
        await context.bot.send_message(update.message.chat.id, text="¡¡¡Ahora estan todos muertos!!!")
    else:
        await context.bot.send_message(update.message.chat.id, text="☠️ ¡¡¡Esto es muy peligroso!!! ☠️")

async def medicion(update: Update, context):
    logging.info(update.message.text)
    sql = f"SELECT timestamp, {update.message.text} FROM mediciones ORDER BY timestamp DESC LIMIT 1"
    conn = await aiomysql.connect(host=os.environ["MARIADB_SERVER"], port=3306,
                                    user=os.environ["MARIADB_USER"],
                                    password=os.environ["MARIADB_USER_PASS"],
                                    db=os.environ["MARIADB_DB"])
    async with conn.cursor() as cur:
        await cur.execute(sql)
        r = await cur.fetchone()
        if update.message.text == 'temperatura':
            unidad = 'ºC'
        else:
            unidad = '%'
        await context.bot.send_message(update.message.chat.id,
                                    text="La última {} es de {} {},\nregistrada a las {:%H:%M:%S %d/%m/%Y}"
                                    .format(update.message.text, str(r[1]).replace('.',','), unidad, r[0]))
        logging.info("La última {} es de {} {}, medida a las {:%H:%M:%S %d/%m/%Y}".format(update.message.text, r[1], unidad, r[0]))
    conn.close()

async def graficos(update: Update, context):
    logging.info(update.message.text)
    sql = f"SELECT timestamp, {update.message.text.split()[1]} FROM mediciones where id mod 2 = 0 AND timestamp >= NOW() - INTERVAL 1 DAY ORDER BY timestamp"
    conn = await aiomysql.connect(host=os.environ["MARIADB_SERVER"], port=3306,
                                    user=os.environ["MARIADB_USER"],
                                    password=os.environ["MARIADB_USER_PASS"],
                                    db=os.environ["MARIADB_DB"])
    async with conn.cursor() as cur:
        await cur.execute(sql)
        filas = await cur.fetchall()

        fig, ax = plt.subplots(figsize=(7, 4))
        fecha,var=zip(*filas)
        ax.plot(fecha,var)
        ax.grid(True, which='both')
        ax.set_title(update.message.text, fontsize=14, verticalalignment='bottom')
        ax.set_xlabel('fecha')
        ax.set_ylabel('unidad')

        buffer = BytesIO()
        fig.tight_layout()
        fig.savefig(buffer, format='png')
        buffer.seek(0)
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=buffer)
    conn.close()

#ACA TERMINA LO COPIADO DEL EJEMPLO DEL BOT

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
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('acercade', acercade))
    application.add_handler(CommandHandler('kill', kill))
    application.add_handler(MessageHandler(filters.Regex("^(temperatura|humedad)$"), medicion))
    application.add_handler(MessageHandler(filters.Regex("^(gráfico temperatura|gráfico humedad)$"), graficos))
    application.run_polling()

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
config['ssl'] = False

# Set up client
MQTTClient.DEBUG = True  # Optional
client = MQTTClient(config)
try:
    asyncio.run(main(client))
finally:
    client.close()
    asyncio.new_event_loop()
