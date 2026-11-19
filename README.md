# Estación meteorológica simulada

TP Integrador — Administración de sistemas GNU/Linux y Virtualización Avanzada (UNSAM).

Un simulador genera mediciones de temperatura y humedad, un backend en Flask las guarda en MySQL y una página servida por NGINX muestra los promedios por día. Tiempo comprimido: **3 minutos reales = 1 día simulado**.

## Arquitectura

~~~
Navegador --:8080--> frontend (NGINX) --/api--> backend (Flask) --> db (MySQL 8.4)
                                                      ^
                                          simulador --+ (POST cada 5 s)
~~~

| Servicio | Imagen base | Puerto publicado |
|---|---|---|
| `db` | [`mysql:8.4`](https://hub.docker.com/_/mysql) | — |
| `backend` | [`python:3.15-alpine`](https://hub.docker.com/_/python) | — |
| `simulador` | [`python:3.15-alpine`](https://hub.docker.com/_/python) | — |
| `frontend` | [`nginx:1.30-alpine`](https://hub.docker.com/_/nginx) | `8080` |

Los servicios se comunican por nombre en la red interna de Compose. Solo el frontend se expone al host. Los datos persisten en el volumen `db_data`.

## Requisitos

- [Docker Engine](https://docs.docker.com/engine/install/) con el plugin Compose.
- Git.

## Puesta en marcha

~~~bash
git clone https://github.com/Molonari/TPFINALLINUX.git
cd TPFINALLINUX
cp .env.example .env      # editar y reemplazar las contraseñas "cambiar"
sudo docker compose up -d --build
~~~

> El primer arranque tarda 2 o 3 minutos mientras MySQL se inicializa. Esperar a que `sudo docker compose ps` muestre `db` y `backend` como `healthy`.

## Acceso

<http://localhost:8080> (o `http://IP-DEL-SERVIDOR:8080` desde otra PC de la red).

## Pruebas

~~~bash
sudo docker compose ps                         # 4 servicios arriba
curl http://localhost:8080/api/promedios       # JSON con promedios por día
sudo docker compose logs -f simulador          # líneas "OK 201"
~~~

## Detención y limpieza

~~~bash
sudo docker compose down          # detiene y conserva los datos
sudo docker compose down -v       # además borra el volumen (base vacía)
~~~

## Componentes

### Base de datos e infraestructura (Franco)

**Archivos**

- `db/Dockerfile`: parte de la imagen oficial `mysql:8.4` (versión fija) y copia `init.sql` a `/docker-entrypoint-initdb.d/`.
- `db/init.sql`: crea la tabla `mediciones`. La imagen de MySQL lo ejecuta **solo en el primer arranque**, cuando el volumen está vacío. Si se modifica, hay que borrar el volumen con `sudo docker compose down -v`.

**Tabla `mediciones`** (base `estacion`)

| Columna | Tipo | Contenido |
|---|---|---|
| `id` | `INT AUTO_INCREMENT` (clave primaria) | Lo asigna MySQL |
| `dia_sim` | `INT` | Día simulado (1, 2, 3...) |
| `hora_sim` | `DECIMAL(4,2)` | Hora simulada, 0.00 a 23.99 (14.50 = 14:30) |
| `temp` | `DECIMAL(5,2)` | Temperatura en °C |
| `hum` | `DECIMAL(5,2)` | Humedad relativa en % |
| `creado_en` | `TIMESTAMP` | Momento real de la inserción (lo completa MySQL) |

- Índice `idx_dia` sobre `dia_sim`: acelera el `GROUP BY dia_sim` que usa `/api/promedios`.
- Se usa `DECIMAL` y no `FLOAT` para guardar los valores exactos.

**Usuarios y contraseñas**

- Las credenciales salen del `.env`, que no se sube al repositorio (está en `.gitignore`). En el repo solo está `.env.example` como plantilla.
- El backend usa el usuario `adminlinux`, que solo tiene permisos sobre la base `estacion`; nunca recibe la contraseña de root.
- MySQL lee estas variables solo al inicializar un volumen vacío: para cambiar una contraseña hay que editar el `.env` y hacer `down -v` (se pierden los datos).

**Persistencia**

- Los datos viven en el volumen con nombre `db_data`, montado en `/var/lib/mysql`.
- `sudo docker compose down` borra los contenedores pero conserva el volumen; `down -v` también borra el volumen.

**Healthcheck y orden de arranque**

- `mysqladmin ping -h 127.0.0.1` cada 5 s. Con `127.0.0.1` la conexión va por TCP, así que no da healthy durante el servidor temporal sin red que la imagen usa para ejecutar `init.sql`.
- `start_period: 120s`: los fallos durante la primera inicialización no cuentan como reintentos. No agrega espera: apenas responde un ping, el servicio pasa a healthy.
- El backend arranca recién cuando `db` está healthy (`depends_on` con `condition: service_healthy`), y el simulador y el frontend esperan al backend.

**Seguridad de red**

- `db` no publica puertos: solo es accesible desde la red interna de Compose, con el nombre `db`.

**Verificar que funciona**

~~~bash
sudo docker compose ps                    # db en (healthy)
sudo docker compose exec db mysql -u adminlinux -p estacion -e "DESCRIBE mediciones;"
sudo docker compose exec db mysql -u adminlinux -p estacion -e "SELECT COUNT(*) FROM mediciones;"
~~~

### Backend (Martín)

API en Flask (`backend/app.py`), escucha en el puerto 5000 dentro de la red de Compose.

| Endpoint | Función |
|---|---|
| `POST /api/mediciones` | Guarda una medición |
| `GET /api/mediciones?limit=N` | Últimas N mediciones |
| `GET /api/promedios` | Promedio, mínimo y máximo por día simulado |
| `GET /health` | Verifica la conexión con la base (lo usa el healthcheck) |

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

## Posibles mejoras

- **Reinicio automático:** agregar `restart: unless-stopped` a los servicios para que Docker los vuelva a levantar si un contenedor se cae o si se reinicia el servidor. Hoy, después de reiniciar la VM, hay que correr `sudo docker compose up -d` a mano.
- **Backups de la base:** hacer copias periódicas con `mysqldump` (por ejemplo con un `cron` en el host), porque el volumen `db_data` está en una sola máquina.
- **Reloj del simulador persistente:** que al arrancar continúe desde el último `dia_sim` guardado en la base, en vez de volver al día 1.
- **Servidor de producción para el backend:** usar `gunicorn` en lugar del servidor de desarrollo de Flask.

## Distribución de responsabilidades

| Integrante | Responsabilidad |
|---|---|
| Franco | Base de datos e infraestructura: servicio `db`, entorno de despliegue |
| Martín | Backend: `app.py`, Dockerfile y servicio `backend` |
| Lautaro | Simulador y frontend |
| Todos | README, revisión cruzada y ensayo de despliegue desde cero |
