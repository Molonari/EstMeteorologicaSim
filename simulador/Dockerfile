FROM python:3.15-alpine

# sin esto los print quedan en el buffer y no se ven en docker logs
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY simulador.py .

CMD ["python", "simulador.py"]
