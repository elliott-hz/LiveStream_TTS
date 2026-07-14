# Script Service Dockerfile
#
# Build:
#   docker build -f services/script-svc/Dockerfile -t script-svc .
#
# Run:
#   docker run -e ENV=dev -p 50051:50051 -p 8081:8081 script-svc

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY libs/ ./libs/
COPY services/script-svc/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime ──
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ENV=production
ENV SERVICE_NAME=script-svc

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /install /usr/local

COPY libs/ ./libs/
COPY services/script-svc/ ./services/script-svc/

RUN pip install -e libs/common -e libs/db --no-deps

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8081/api/v1/health || exit 1

EXPOSE 8081 50051

CMD ["python", "-m", "services.script-svc.src.main"]
