FROM python:3.13-slim

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Instalar dependencias del sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Crear directorios necesarios
COPY . .

# Crear directorio de logs
RUN mkdir -p logs

# Comando por defecto
CMD ["python", "-m", "src.main"]