FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# Убедитесь, что Flask слушает 0.0.0.0, а не 127.0.0.1
CMD ["python", "run.py"]