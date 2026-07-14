# Stream Service Dockerfile
#
# Build: docker build -f services/stream-svc/Dockerfile -t stream-svc .

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY libs/ ./libs/
COPY services/stream-svc/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime ──
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ENV=production
ENV SERVICE_NAME=stream-svc

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /install /usr/local

COPY libs/ ./libs/
COPY services/stream-svc/ ./services/stream-svc/

RUN pip install -e libs/common -e libs/db --no-deps

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8084/api/v1/health || exit 1

EXPOSE 8084 50054

CMD ["python", "-m", "services.stream-svc.src.main"]
