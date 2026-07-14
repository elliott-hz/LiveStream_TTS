# platform-svc Dockerfile
# Unified management service — runs all 11 business modules in one process.
FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libffi-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install shared libs first
COPY libs/common/ /app/libs/common/
COPY libs/db/ /app/libs/db/
COPY libs/kafka/ /app/libs/kafka/
COPY libs/proto/ /app/libs/proto/

# Install platform-svc dependencies
COPY services/platform-svc/requirements.txt /app/services/platform-svc/
RUN pip install --no-cache-dir -r /app/services/platform-svc/requirements.txt


FROM python:3.11-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy application code
COPY libs/ /app/libs/
COPY services/platform-svc/ /app/services/platform-svc/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 50050 8081
HEALTHCHECK --interval=15s --timeout=3s --retries=3 CMD curl -f http://localhost:8081/api/v1/health || exit 1

CMD ["python", "-m", "services.platform_svc.src.main"]
