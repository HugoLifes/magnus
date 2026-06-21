# Imagen del daemon de Magnus.
#
# Base CUDA para poder hablar con la GPU (vLLM/TensorRT-LLM se añaden con el
# extra [serve] cuando se quiera servir modelos desde dentro del contenedor).
# Para el destino B200 / GB200, elegir el tag CUDA acorde al driver del host.
#
# Nota de arquitectura: si el host es x86 (DGX/HGX B200) usa la imagen amd64;
# si es Grace/ARM (GB200, DGX Spark) usa la variante arm64. Docker elige según
# la plataforma del build, pero déjalo explícito en CI.
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY core ./core
COPY daemon ./daemon
COPY cli ./cli

EXPOSE 8420
# Escucha en 0.0.0.0 dentro del contenedor; expón el puerto con cuidado (ver compose).
CMD ["uvicorn", "daemon.app:api", "--host", "0.0.0.0", "--port", "8420"]
