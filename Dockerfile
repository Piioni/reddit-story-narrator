FROM python:3.13-slim

# Instalar dependencias del sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev && \
    rm -rf /var/lib/apt/lists/*


WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


# Crear directorios necesarios
COPY src/ src/
COPY config/ config/

# Crear directorio de logs
RUN mkdir -p /app/logs && chmod 777 /app/logs

# Comando por defecto
CMD ["python", "src/main.py"]