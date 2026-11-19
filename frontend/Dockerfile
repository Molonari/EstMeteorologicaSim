FROM nginx:1.30-alpine

# reemplaza la configuracion por defecto por la nuestra (con el proxy a /api/)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# la pagina
COPY html/ /usr/share/nginx/html/
