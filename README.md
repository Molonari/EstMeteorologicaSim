
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
