# Simulador de estacion meteorologica
# Cada INTERVALO segundos genera una medicion y la manda al backend por HTTP.
# Tiempo comprimido: SEGUNDOS_POR_DIA segundos reales = 1 dia simulado.

import json
import math
import os
import random
import time
import urllib.request

BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:5000/api/mediciones")
INTERVALO = float(os.environ.get("INTERVALO", "5"))
SEGUNDOS_POR_DIA = float(os.environ.get("SEGUNDOS_POR_DIA", "180"))

inicio = time.time()


def tiempo_simulado():
    transcurrido = time.time() - inicio
    dia = int(transcurrido // SEGUNDOS_POR_DIA) + 1
    hora = (transcurrido % SEGUNDOS_POR_DIA) / SEGUNDOS_POR_DIA * 24
    # trunco a 2 decimales para que nunca llegue a 24.00
    hora = math.floor(hora * 100) / 100
    return dia, hora


def generar_medicion(hora):
    # temperatura: curva diaria con minimo a las 3 y maximo a las 15, mas ruido
    curva = math.sin(2 * math.pi * (hora - 9) / 24)
    temp = 15 + 7 * curva + random.uniform(-0.5, 0.5)
    # humedad: al reves que la temperatura (alta de noche, baja de dia)
    hum = 65 - 15 * curva + random.uniform(-2, 2)
    return round(temp, 2), round(hum, 2)


def enviar(medicion):
    datos = json.dumps(medicion).encode()
    pedido = urllib.request.Request(
        BACKEND_URL, data=datos, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(pedido, timeout=5) as respuesta:
        return respuesta.status


print("Simulador iniciado, enviando a", BACKEND_URL)

while True:
    dia, hora = tiempo_simulado()
    temp, hum = generar_medicion(hora)
    medicion = {"dia_sim": dia, "hora_sim": hora, "temp": temp, "hum": hum}
    try:
        estado = enviar(medicion)
        print("OK", estado, medicion)
    except Exception as e:
        # si el backend no responde no cortamos: se vuelve a intentar en la proxima vuelta
        print("ERROR al enviar", medicion, "->", e)
    time.sleep(INTERVALO)
