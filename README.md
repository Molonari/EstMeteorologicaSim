# Estación meteorológica simulada

Trabajo Práctico Integrador — Administración de sistemas GNU/Linux y Virtualización Avanzada (UNSAM).

Infraestructura de 4 contenedores orquestada con Docker Compose: un simulador genera mediciones de temperatura y humedad, un backend en Flask las guarda en MySQL y calcula promedios por día, y una página web servida por NGINX las muestra. El tiempo está comprimido: **3 minutos reales = 1 día simulado**.

## Arquitectura

~~~
 Navegador
    |  http://IP-DEL-SERVIDOR:8080
    v
+-----------+   /api/*    +-----------+   SQL    +-----------+
| frontend  | ----------> |  backend  | -------> |    db     |
|  NGINX    |             |  Flask    |          | MySQL 8.4 |
+-----------+             +-----------+          +-----------+
                               ^                       |
               POST /api/mediciones                volumen
                               |                   db_data
                         +-----------+
                         | simulador |
                         +-----------+
~~~

| Servicio | Imagen base | Función | Puerto publicado |
|---|---|---|---|
| `db` | `mysql:8.4` | Guarda las mediciones (tabla `mediciones`) | — |
| `backend` | `python:3.15-alpine` | API HTTP: recibe mediciones y calcula promedios | — |
| `simulador` | `python:3.15-alpine` | Genera una medición cada 5 s y la envía al backend | — |
| `frontend` | `nginx:1.30-alpine` | Sirve la página y hace de proxy de `/api/` al backend | `8080` |

- Todos los servicios están en la red interna que crea Compose y se encuentran por nombre (`db`, `backend`).
- Solo el frontend publica un puerto al host. La base y el backend no son accesibles desde afuera.
- Orden de arranque (`depends_on` con `condition: service_healthy`): `db` → `backend` → `simulador` y `frontend`.
- Los datos de MySQL persisten en el volumen con nombre `db_data`.

Imágenes oficiales utilizadas:

- MySQL: <https://hub.docker.com/_/mysql>
- Python: <https://hub.docker.com/_/python>
- NGINX: <https://hub.docker.com/_/nginx>

## Requisitos

- Linux con Docker Engine y el plugin Docker Compose (probado con Docker 29.x y Compose v5.x sobre Ubuntu 26.04).
- Git y acceso a internet para descargar las imágenes la primera vez.
- Puerto `8080` libre en el host.

Los comandos usan `sudo` porque el usuario no pertenece al grupo `docker` (pertenecer a ese grupo equivale a tener acceso root).

## Puesta en marcha

~~~bash
git clone https://github.com/Molonari/TPFINALLINUX.git
cd TPFINALLINUX
cp .env.example .env
nano .env                       # reemplazar los valores "cambiar" por contraseñas propias
sudo docker compose up -d --build
sudo docker compose ps
~~~

Variables del `.env` (el archivo real no se sube al repositorio):

| Variable | Uso |
|---|---|
| `MYSQL_ROOT_PASSWORD` | Contraseña de root de MySQL (solo administración) |
| `MYSQL_DATABASE` | Base que se crea al iniciar (`estacion`) |
| `MYSQL_USER` | Usuario de la aplicación (`adminlinux`) |
| `MYSQL_PASSWORD` | Contraseña de ese usuario (la usa el backend) |

**El primer arranque tarda 2 a 3 minutos:** MySQL inicializa la base desde cero. Repetir `sudo docker compose ps` hasta ver `db` y `backend` en `(healthy)`. Los arranques siguientes tardan segundos.

## Acceso

- Página: <http://localhost:8080> desde el servidor, o `http://IP-DEL-SERVIDOR:8080` desde otra PC de la red (la IP se ve con `ip a`).
- API (a través del proxy): `http://IP-DEL-SERVIDOR:8080/api/promedios` y `/api/mediciones?limit=N`.

## Pruebas

~~~bash
sudo docker compose ps                              # 4 servicios arriba; db y backend (healthy)
curl http://localhost:8080/api/promedios            # JSON con promedios por día (pasa por NGINX)
curl http://localhost:5000/health                   # debe FALLAR: el backend no está expuesto
sudo docker compose logs -f simulador               # líneas "OK 201 {...}"
sudo docker compose exec db mysql -u adminlinux -p estacion -e "SELECT COUNT(*) FROM mediciones;"
~~~

## Detención

~~~bash
sudo docker compose down        # baja los contenedores; los datos del volumen se conservan
~~~

## Limpieza

~~~bash
sudo docker compose down -v --rmi local   # borra contenedores, red, volumen db_data e imágenes construidas
~~~

## Componentes

### Base de datos

> Sección a completar por Franco.

- `db/Dockerfile`: parte de `mysql:8.4` y copia `init.sql` a `/docker-entrypoint-initdb.d/`, que la imagen ejecuta solo en el primer arranque (con el volumen vacío). Si se modifica `init.sql`, hay que borrar el volumen con `down -v`.
- `db/init.sql`: crea la tabla `mediciones` (`id`, `dia_sim`, `hora_sim`, `temp`, `hum`, `creado_en`) con un índice por `dia_sim`.
- Healthcheck: `mysqladmin ping -h 127.0.0.1`. Con `127.0.0.1` la conexión va por TCP, así que no marca healthy durante el servidor temporal sin red que usa la imagen para ejecutar `init.sql`. `start_period: 120s` cubre la primera inicialización.

### Backend

- `backend/app.py`: API en Flask, escucha en `0.0.0.0:5000`. Se conecta a MySQL con el host `db` y el usuario de la aplicación (no recibe la contraseña de root).

| Endpoint | Función |
|---|---|
| `GET /health` | Hace `SELECT 1` contra la base: 200 si conecta, 503 si no. Lo usa el healthcheck |
| `POST /api/mediciones` | Guarda una medición `{"dia_sim", "hora_sim", "temp", "hum"}`; 400 si faltan campos |
| `GET /api/mediciones?limit=N` | Últimas N mediciones (por defecto 20, máximo 500) |
| `GET /api/promedios` | Promedio, mínimo y máximo de temperatura y humedad por día simulado |

- `backend/requirements.txt`: `flask`, `pymysql` y `cryptography` (necesaria para autenticarse contra MySQL 8.4 con `caching_sha2_password`), con versiones fijadas.
- `backend/Dockerfile`: parte de `python:3.15-alpine`; copia `requirements.txt` e instala dependencias antes de copiar `app.py`, para aprovechar la caché de capas.
  
## Simulador (Lautaro)

Genera mediciones falsas de temperatura y humedad y las manda al backend por HTTP, como si fuera un sensor real.

**Archivos**

- `simulador/simulador.py`: el script. Solo usa la libreria estandar de Python, no hay que instalar nada.
- `simulador/Dockerfile`: parte de `python:3.15-alpine` (la misma imagen que el backend) y copia el script.

**Tiempo simulado**

3 minutos reales equivalen a 1 dia simulado. El reloj lo lleva el simulador a partir de los segundos que pasaron desde que arranco:

- `dia_sim = (segundos // 180) + 1`
- `hora_sim = (segundos % 180) / 180 * 24` (con 2 decimales, 14.50 = 14:30)

Como manda una medicion cada 5 segundos, cada dia simulado tiene 180 / 5 = 36 mediciones.

**Como genera los datos**

- Temperatura: curva senoidal de 24 h con minimo a las 3 y maximo a las 15 (entre 8 y 22 grados aprox.) mas un poco de ruido aleatorio.
- Humedad: la misma curva invertida (alta de noche, baja de dia), entre 50 y 80 % aprox.

Cada medicion se manda con `POST /api/mediciones`:

~~~json
{"dia_sim": 3, "hora_sim": 14.5, "temp": 24.37, "hum": 58.2}
~~~

Si el backend no responde, el error se muestra en el log y se vuelve a intentar en la proxima vuelta; el contenedor no se cae.

**Variables de entorno** (se cambian en el servicio `simulador` del `docker-compose.yml`)

| Variable | Valor por defecto | Que controla |
|---|---|---|
| `BACKEND_URL` | `http://backend:5000/api/mediciones` | A donde manda las mediciones |
| `INTERVALO` | `5` | Segundos entre mediciones |
| `SEGUNDOS_POR_DIA` | `180` | Segundos reales que dura un dia simulado |

Por ejemplo, para que un dia dure 1 minuto: `SEGUNDOS_POR_DIA: 60` y `sudo docker compose up -d`.

**Verificar que funciona**

~~~bash
sudo docker compose logs -f simulador
~~~

Cada linea tiene que decir `OK 201 {...}` (201 = medicion guardada).

**Limitacion conocida:** el reloj vuelve al dia 1 cada vez que se reinicia el contenedor del simulador. Si se reinicia sin borrar la base, se repiten numeros de dia. Para empezar de cero: `sudo docker compose down -v`.

## Frontend (Lautaro)

Pagina web que muestra los datos. La sirve NGINX, que ademas hace de proxy hacia el backend.

**Archivos**

- `frontend/html/index.html`: la pagina. Muestra los promedios por dia y las ultimas 20 mediciones, y se actualiza cada 5 segundos.
- `frontend/nginx.conf`: configuracion de NGINX. Sirve la pagina y reenvia todo lo que empieza con `/api/` a `http://backend:5000`.
- `frontend/Dockerfile`: parte de la imagen oficial `nginx:1.30-alpine` (rama stable) y copia la configuracion y la pagina.

**Acceso**

Es el unico servicio con puerto publicado (`8080:80`):

- Desde la misma maquina: <http://localhost:8080>
- Desde otra PC de la red: `http://IP-DEL-SERVIDOR:8080` (la IP se ve con `ip a`)

**Por que el proxy**

El JavaScript de la pagina corre en el navegador del usuario, fuera de la red de Compose, donde el nombre `backend` no existe. Por eso la pagina pide `/api/...` al mismo NGINX que la sirvio, y NGINX (que si esta en la red) lo reenvia al backend:

~~~
Navegador --/api/promedios--> NGINX (frontend:80) --> backend:5000/api/promedios
~~~

**Verificar que funciona**

~~~bash
curl localhost:8080                  # devuelve el HTML de la pagina
curl localhost:8080/api/promedios    # devuelve JSON del backend, pasando por NGINX
~~~

**Modificar la pagina:** el `index.html` se copia dentro de la imagen, asi que despues de cambiarlo hay que reconstruir: `sudo docker compose up -d --build`.

## Distribución de responsabilidades

| Integrante | Responsabilidad |
|---|---|
| Franco | Base de datos e infraestructura: servicio `db`, entorno de despliegue |
| Martín | Backend: `app.py`, Dockerfile y servicio `backend` |
| Lautaro | Simulador y frontend |
| Todos | README, revisión cruzada y ensayo de despliegue desde cero |
