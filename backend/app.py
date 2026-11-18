# Backend de la estación meteorológica simulada.
# Recibe mediciones del simulador, las guarda en MySQL y las expone
# en JSON para el frontend.

import os
from decimal import Decimal

import pymysql
from flask import Flask, jsonify, request

app = Flask(__name__)

# Datos de conexión. Llegan como variables de entorno desde el compose
# (que a su vez las lee del .env). Nada de contraseñas en el código.
# "db" es el nombre del servicio de la base en la red de Compose.
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "db"),
    "user": os.environ["MYSQL_USER"],
    "password": os.environ["MYSQL_PASSWORD"],
    "database": os.environ["MYSQL_DATABASE"],
    "cursorclass": pymysql.cursors.DictCursor,
}

CAMPOS = ("dia_sim", "hora_sim", "temp", "hum")


def conectar():
    # Una conexión nueva por pedido: simple, y si la base se reinicia
    # el backend se recupera solo en el pedido siguiente.
    return pymysql.connect(**DB_CONFIG)


def a_json(fila):
    # MySQL devuelve DECIMAL como Decimal y TIMESTAMP como datetime.
    # Los pasamos a float y a texto ISO para que el JSON sea simple.
    limpia = {}
    for clave, valor in fila.items():
        if isinstance(valor, Decimal):
            valor = float(valor)
        elif hasattr(valor, "isoformat"):
            valor = valor.isoformat()
        limpia[clave] = valor
    return limpia


@app.get("/health")
def health():
    # Lo usa el healthcheck de Compose: si responde, el backend está vivo.
    return jsonify(status="ok")


@app.post("/api/mediciones")
def crear_medicion():
    # Lo llama el simulador con un JSON:
    # {"dia_sim": 3, "hora_sim": 14.5, "temp": 24.37, "hum": 58.2}
    datos = request.get_json(silent=True)
    if not datos or any(campo not in datos for campo in CAMPOS):
        return jsonify(error=f"Faltan campos. Se esperan: {', '.join(CAMPOS)}"), 400

    con = conectar()
    try:
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO mediciones (dia_sim, hora_sim, temp, hum) "
                "VALUES (%s, %s, %s, %s)",
                (datos["dia_sim"], datos["hora_sim"], datos["temp"], datos["hum"]),
            )
            nuevo_id = cur.lastrowid
        con.commit()
    finally:
        con.close()
    return jsonify(id=nuevo_id), 201


@app.get("/api/mediciones")
def listar_mediciones():
    # Últimas N mediciones, la más nueva primero. ?limit=N (por defecto 20).
    limite = request.args.get("limit", default=20, type=int)
    limite = max(1, min(limite, 500))

    con = conectar()
    try:
        with con.cursor() as cur:
            cur.execute(
                "SELECT id, dia_sim, hora_sim, temp, hum, creado_en "
                "FROM mediciones ORDER BY id DESC LIMIT %s",
                (limite,),
            )
            filas = cur.fetchall()
    finally:
        con.close()
    return jsonify([a_json(f) for f in filas])


@app.get("/api/promedios")
def promedios():
    # Promedio, mínimo y máximo de temp y hum por día simulado.
    con = conectar()
    try:
        with con.cursor() as cur:
            cur.execute(
                "SELECT dia_sim, COUNT(*) AS mediciones, "
                "ROUND(AVG(temp), 2) AS temp_prom, "
                "MIN(temp) AS temp_min, MAX(temp) AS temp_max, "
                "ROUND(AVG(hum), 2) AS hum_prom, "
                "MIN(hum) AS hum_min, MAX(hum) AS hum_max "
                "FROM mediciones GROUP BY dia_sim ORDER BY dia_sim"
            )
            filas = cur.fetchall()
    finally:
        con.close()
    return jsonify([a_json(f) for f in filas])


if __name__ == "__main__":
    # 0.0.0.0 = escuchar en todas las interfaces del contenedor.
    # Con 127.0.0.1 solo aceptaría conexiones desde adentro del propio
    # contenedor, y ni el simulador ni NGINX podrían llegar.
    app.run(host="0.0.0.0", port=5000)
