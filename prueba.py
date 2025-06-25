import machine
import time

adc = machine.ADC(machine.Pin(4))  # O cualquier otro pin ADC
adc.atten(machine.ADC.ATTN_11DB)
adc.width(machine.ADC.WIDTH_12BIT)

while True:
    try:
        raw = adc.read()
        volt = raw * (3.3 / 4095)
        print("RAW:", raw, "Voltaje:", volt)
    except Exception as e:
        print("Error al leer ADC:", e)
    time.sleep(1)