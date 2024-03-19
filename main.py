import dht, machine
import time

d = dht.DHT22(machine.Pin(25))

while True:
    d.measure()
    d.temperature()
    d.humidity()
    print("La temperatura es: ",d.temperature())
    print("La humedad es: ",d.humidity())
    time.sleep(2)