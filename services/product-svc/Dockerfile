# ──────────────────────────────────────────────────────────
# Multi-stage Docker Build for product-svc
# Build context: repository root (to access libs/)
#
# Build:
#   docker build -f services/product-svc/Dockerfile -t product-svc .
# ──────────────────────────────────────────────────────────

# ── Stage 1: Dependencies ──
FROM python:3.11-slim AS builder

ARG SERVICE_NAME=product-svc
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy shared libs first
COPY libs/ ./libs/
COPY services/${SERVICE_NAME}/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --prefix=/install \
    -r requirements.txt

# ── Stage 2: Runtime ──
FROM python:3.11-slim AS runtime

ARG SERVICE_NAME=product-svc
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=${SERVICE_NAME}
ENV ENV=production

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages
COPY --from=builder /install /usr/local

# Copy shared libs + service source
COPY libs/ ./libs/
COPY services/${SERVICE_NAME}/ ./services/${SERVICE_NAME}/

# Install shared libs as editable packages
RUN pip install -e libs/common -e libs/db -e libs/kafka --no-deps

# Health check
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:${HTTP_PORT:-8003}/api/v1/health || exit 1

EXPOSE ${HTTP_PORT:-8003} ${GRPC_PORT:-50051}

CMD ["sh", "-c", "python services/product-svc/src/main.py"]
