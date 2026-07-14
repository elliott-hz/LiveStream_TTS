# TTS Service Dockerfile
# GPU-enabled build for CosyVoice2 + TensorRT
#
# Build: docker build -f services/tts-svc/Dockerfile -t tts-svc .

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY libs/ ./libs/
COPY services/tts-svc/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime (GPU) ──
FROM nvidia/cuda:12.1-runtime-ubuntu22.04 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ENV=production
ENV SERVICE_NAME=tts-svc

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3-pip libsndfile1 curl \
    && rm -rf /var/lib/apt/lists/* \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

WORKDIR /app

COPY --from=builder /install /usr/local

COPY libs/ ./libs/
COPY services/tts-svc/ ./services/tts-svc/

RUN pip install -e libs/common -e libs/db --no-deps

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/v1/health || exit 1

EXPOSE 8080 50051

CMD ["python", "-m", "services.tts-svc.src.main"]
