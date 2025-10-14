FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# Убедитесь, что Flask слушает 0.0.0.0, а не 127.0.0.1
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Порт остаётся 5000
EXPOSE 5000

CMD ["gunicorn", \
     "-k", "eventlet", \
     "-w", "1", \
     "-b", "0.0.0.0:5000", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "run:app"]