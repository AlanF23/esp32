# Germán Andrés Xander 2023

from machine import Pin
import time

print("esperando pulsador")

sw = Pin(23, Pin.IN)
led = Pin(2, Pin.OUT)
contador = 0
flag=True

while True:
    if sw.value() and flag:
        flag = False
        led.value(not led.value())
        contador =+ 1
        print(contador)
    if not sw.value():
        flag = True
    time.sleep_ms(5)