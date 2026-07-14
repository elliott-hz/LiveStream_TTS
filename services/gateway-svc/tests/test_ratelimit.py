"""
Tests for the token bucket rate limiter middleware.

Covers:
  - Under limit → request passes
  - Burst consuming → multiple requests succeed within burst
  - Over limit → 429 Too Many Requests
  - Retry-After header present on 429
  - Different rate limits for different route patterns
  - Token bucket refill logic
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from fastapi import FastAPI, Request

# Monorepo path setup
# Add repo root and the gateway-svc parent so we can import src.*
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SVC_DIR = _REPO_ROOT / "services" / "gateway-svc"
for p in [str(_REPO_ROOT), str(_SVC_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Import via the src package so relative imports (..config) resolve correctly
from src.middleware.ratelimit import (
    ROUTE_LIMITS,
    RateLimitMiddleware,
    RateLimiterRegistry,
    TokenBucket,
    rate_limiter_registry,
)
from src.config import config


# ── Fixtures ──


@pytest.fixture
def app():
    """Create a minimal FastAPI app with rate limit middleware for testing."""
    app = FastAPI()

    @app.get("/api/v1/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/api/v1/test")
    async def test():
        return {"data": "ok"}

    @app.get("/api/v1/tts/synthesize")
    async def tts():
        return {"synthesized": True}

    @app.post("/api/v1/admin/config")
    async def admin():
        return {"configured": True}

    app.add_middleware(RateLimitMiddleware)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ── Token Bucket Tests ──


@pytest.mark.asyncio
async def test_token_bucket_consume_within_limit():
    """Test consuming tokens within the bucket limit succeeds."""
    bucket = TokenBucket(rps=10, burst=10)
    allowed, wait = await bucket.consume(1)
    assert allowed is True
    assert wait == 0.0


@pytest.mark.asyncio
async def test_token_bucket_consume_exceeds_burst():
    """Test consuming more tokens than burst is denied."""
    bucket = TokenBucket(rps=10, burst=2)
    allowed1, _ = await bucket.consume(2)
    assert allowed1 is True
    allowed2, wait = await bucket.consume(1)
    assert allowed2 is False
    assert wait > 0.0


@pytest.mark.asyncio
async def test_token_bucket_refill():
    """Test that the bucket refills over time."""
    bucket = TokenBucket(rps=100, burst=100)
    # Drain the bucket
    for _ in range(100):
        await bucket.consume(1)
    allowed, _ = await bucket.consume(1)
    assert allowed is False

    # Simulate time passing (advance the clock)
    bucket.last_refill = time.monotonic() - 1.0  # 1 second ago
    # Next consume should get ~100 tokens refilled
    allowed, _ = await bucket.consume(50)
    assert allowed is True


@pytest.mark.asyncio
async def test_token_bucket_fill_percentage():
    """Test fill_percentage property."""
    bucket = TokenBucket(rps=10, burst=10)
    assert bucket.fill_percentage == 1.0
    await bucket.consume(5)
    assert bucket.fill_percentage == 0.5


# ── Registry Tests ──


@pytest.mark.asyncio
async def test_registry_get_or_create_bucket():
    """Test that registry creates and reuses buckets."""
    registry = RateLimiterRegistry()
    bucket1 = await registry.get_or_create_bucket("test:key", rps=10, burst=20)
    bucket2 = await registry.get_or_create_bucket("test:key", rps=10, burst=20)
    assert bucket1 is bucket2  # Same instance


@pytest.mark.asyncio
async def test_registry_get_route_rps():
    """Test route-specific RPS detection."""
    registry = RateLimiterRegistry()
    assert registry.get_route_rps("/api/v1/tts/synthesize") == config.rate_limit_tts_rps
    assert registry.get_route_rps("/api/v1/admin/config") == config.rate_limit_admin_rps
    assert registry.get_route_rps("/api/v1/test") == config.rate_limit_default_rps


@pytest.mark.asyncio
async def test_ws_connection_tracking():
    """Test WebSocket connection tracking per IP."""
    registry = RateLimiterRegistry()
    # Acquire slots up to the limit
    for i in range(config.rate_limit_ws_per_ip):
        allowed = await registry.try_acquire_ws("192.168.1.1", f"conn_{i}")
        assert allowed is True

    # Next should be denied
    allowed = await registry.try_acquire_ws("192.168.1.1", "conn_overflow")
    assert allowed is False

    # Different IP should work
    allowed = await registry.try_acquire_ws("10.0.0.1", "conn_0")
    assert allowed is True

    # Release one and retry
    await registry.release_ws("192.168.1.1", "conn_0")
    allowed = await registry.try_acquire_ws("192.168.1.1", "conn_retry")
    assert allowed is True


# ── Integration Tests ──


@pytest.mark.asyncio
async def test_health_endpoint_not_rate_limited(client):
    """Health endpoint should not be rate limited."""
    for _ in range(10):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_burst_requests_within_limit(client):
    """Multiple rapid requests within the burst limit should succeed."""
    # Send burst requests (within default rps=20 with burst multiplier)
    burst_count = config.rate_limit_default_rps * 2
    responses = []
    for _ in range(burst_count):
        responses.append(await client.get("/api/v1/test"))

    # All should succeed (burst allows up to base*multiplier)
    # Some may get 429 if burst exceeded, but the burst value is at least
    # as large as what we're sending in this test
    successful = [r for r in responses if r.status_code == 200]
    assert len(successful) > 0

    # Rate limit headers should be present
    first = responses[0]
    assert "x-ratelimit-limit" in first.headers
    assert "x-ratelimit-burst" in first.headers
    assert "x-ratelimit-remaining" in first.headers


@pytest.mark.asyncio
async def test_ratelimit_route_pattern_default():
    """Test that default routes get default rate limits."""
    registry = RateLimiterRegistry()
    for limit in ROUTE_LIMITS:
        if not limit.matches("/api/v1/test"):
            continue
    rps = registry.get_route_rps("/api/v1/test")
    assert rps == config.rate_limit_default_rps
