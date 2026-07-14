# ──────────────────────────────────────────────────────────
# Multi-stage Docker Build for knowledge-svc
# Build context: repository root (to access libs/)
#
# Build:
#   docker build -f services/knowledge-svc/Dockerfile -t knowledge-svc .
# ──────────────────────────────────────────────────────────

# ── Stage 1: Dependencies ──
FROM python:3.11-slim AS builder

ARG SERVICE_NAME=knowledge-svc
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY libs/ ./libs/
COPY services/${SERVICE_NAME}/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --prefix=/install \
    -r requirements.txt

# ── Stage 2: Runtime ──
FROM python:3.11-slim AS runtime

ARG SERVICE_NAME=knowledge-svc
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=${SERVICE_NAME}
ENV ENV=production

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /install /usr/local

COPY libs/ ./libs/
COPY services/${SERVICE_NAME}/ ./services/${SERVICE_NAME}/

RUN pip install -e libs/common -e libs/db -e libs/kafka --no-deps

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:${HTTP_PORT:-8008}/api/v1/health || exit 1

EXPOSE ${HTTP_PORT:-8008} ${GRPC_PORT:-50051}

CMD ["sh", "-c", "python services/knowledge-svc/src/main.py"]
