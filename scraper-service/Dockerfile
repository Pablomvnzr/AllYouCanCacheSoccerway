FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema necesarias para que Chromium (Playwright) funcione
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instala Chromium y sus dependencias del sistema operativo
RUN playwright install --with-deps chromium

COPY src/ ./src/

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
