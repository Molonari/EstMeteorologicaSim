FROM python:3.15-alpine

#hace instantaneos los logs de py para que no se pierdan en el buffer
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

#puerto donde escucha flask
EXPOSE 5000

CMD ["python","app.py"]
