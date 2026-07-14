# ── Multi-stage Docker Build for user-svc ──
# Build context: repository root (to access libs/)
#
# Build:   docker build -f services/user-svc/Dockerfile -t user-svc .
# Run:     docker run -p 50051:50051 -p 8080:8080 user-svc

# ── Stage 1: Dependencies ──
FROM python:3.11-slim AS builder

ARG SERVICE_NAME=user-svc
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy shared libs first (they change less frequently)
COPY libs/ ./libs/
COPY services/${SERVICE_NAME}/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --prefix=/install \
    -r requirements.txt

# ── Stage 2: Runtime ──
FROM python:3.11-slim AS runtime

ARG SERVICE_NAME=user-svc
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

# Copy service source + shared libs
COPY libs/ ./libs/
COPY services/${SERVICE_NAME}/ ./services/${SERVICE_NAME}/

# Install shared libs as editable packages
RUN pip install -e libs/common -e libs/db -e libs/kafka --no-deps

# Health check
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/v1/health || exit 1

EXPOSE 8080 50051

# Launch the service
CMD ["sh", "-c", "python -m services.${SERVICE_NAME}.src.main"]
