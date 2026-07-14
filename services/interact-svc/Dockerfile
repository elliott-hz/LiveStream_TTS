# ── Builder Stage ──
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY services/interact-svc/requirements.txt services/interact-svc/requirements.txt
COPY libs/common libs/common
COPY libs/proto libs/proto

# Install dependencies to a temporary prefix
RUN pip install --prefix=/install \
    -r services/interact-svc/requirements.txt

# ── Runtime Stage ──
FROM python:3.11-slim

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy source code
COPY services/interact-svc services/interact-svc
COPY libs/common libs/common
COPY libs/proto libs/proto

# Service metadata
ENV SERVICE_NAME=interact-svc
ENV PYTHONPATH=/app

# Expose gRPC port (50051) and HTTP port (8080)
EXPOSE 50051 8080

# Health check
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/api/v1/health || exit 1

# Run with uvicorn (HTTP) — gRPC runs in-process on separate port
CMD ["python", "-m", "services.interact-svc.src.main"]
