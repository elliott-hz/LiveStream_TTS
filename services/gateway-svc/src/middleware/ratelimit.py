"""
Token bucket rate limiter middleware for FastAPI.

In-memory implementation (Redis-backed in production).
Returns 429 Too Many Requests with Retry-After header when limits are exceeded.

Rate limits:
  - Admin routes:  100 req/s (configurable via RATE_LIMIT_ADMIN_RPS)
  - TTS routes:     50 req/s (configurable via RATE_LIMIT_TTS_RPS)
  - Default:        20 req/s (configurable via RATE_LIMIT_DEFAULT_RPS)
  - WebSocket:       5 conn/IP (configurable via RATE_LIMIT_WS_PER_IP)
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import defaultdict
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from libs.common.logging import get_logger

from ..config import config

logger = get_logger(__name__)

# ── Route rate limit configuration ──


class RouteRateLimit:
    """Rate limit configuration for a route pattern."""

    def __init__(
        self,
        pattern: str,
        rps: int,
        burst_multiplier: int | None = None,
    ):
        self.pattern = pattern
        self.rps = rps
        self.burst = rps * (burst_multiplier or config.rate_limit_burst_multiplier)

    def matches(self, path: str) -> bool:
        """Check if the path matches this route pattern."""
        return path.startswith(self.pattern)


# Route-level rate limits (applied after prefix matching)
ROUTE_LIMITS: list[RouteRateLimit] = [
    RouteRateLimit("/api/v1/admin", config.rate_limit_admin_rps),
    RouteRateLimit("/api/v1/tts", config.rate_limit_tts_rps),
    RouteRateLimit("/api/v1/ws/tts", config.rate_limit_tts_rps),
    # Default is applied via fallback
]

# WebSocket connection tracking (per IP)
WS_BUCKET_KEY_PREFIX = "ws:"


# ── Token Bucket ──


class TokenBucket:
    """In-memory token bucket rate limiter.

    Thread-safe via asyncio.Lock. Redis-backed in production.
    """

    def __init__(self, rps: int, burst: int | None = None) -> None:
        self.rate = rps  # tokens per second
        self.burst = burst or rps
        self.tokens = float(self.burst)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> tuple[bool, float]:
        """Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume (default 1).

        Returns:
            Tuple of (allowed: bool, wait_seconds: float).
            If allowed is False, wait_seconds indicates how long to wait.
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill

            # Refill tokens based on elapsed time
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0.0
            else:
                wait = (tokens - self.tokens) / self.rate
                return False, wait

    @property
    def fill_percentage(self) -> float:
        """Current fill percentage (0.0 - 1.0)."""
        return self.tokens / self.burst if self.burst > 0 else 0.0


# ── Bucket registry ──


class RateLimiterRegistry:
    """Manages token buckets for all rate-limited resources.

    Buckets are keyed by a unique key (e.g., "route:/api/v1/tts" or "ip:127.0.0.1").
    """

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}
        self._ws_connections: dict[str, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def get_or_create_bucket(
        self, key: str, rps: int, burst: int | None = None
    ) -> TokenBucket:
        """Get or create a token bucket for the given key."""
        async with self._lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(rps, burst)
            return self._buckets[key]

    def get_route_rps(self, path: str) -> int:
        """Get the rate limit RPS for a given path."""
        for limit in ROUTE_LIMITS:
            if limit.matches(path):
                return limit.rps
        return config.rate_limit_default_rps

    def get_route_burst(self, path: str) -> int:
        """Get the burst limit for a given path."""
        for limit in ROUTE_LIMITS:
            if limit.matches(path):
                return limit.burst
        return config.rate_limit_default_rps * config.rate_limit_burst_multiplier

    # ── WebSocket connection tracking ──

    async def try_acquire_ws(self, client_ip: str, connection_id: str) -> bool:
        """Try to acquire a WebSocket connection slot for an IP.

        Returns True if under the limit, False if limit exceeded.
        """
        async with self._lock:
            connections = self._ws_connections[client_ip]
            if len(connections) >= config.rate_limit_ws_per_ip:
                return False
            connections.add(connection_id)
            return True

    async def release_ws(self, client_ip: str, connection_id: str) -> None:
        """Release a WebSocket connection slot."""
        async with self._lock:
            connections = self._ws_connections.get(client_ip)
            if connections:
                connections.discard(connection_id)
                if not connections:
                    del self._ws_connections[client_ip]

    async def cleanup_stale(self) -> None:
        """Periodic cleanup of stale buckets (for memory management)."""
        async with self._lock:
            now = time.monotonic()
            stale_keys = []
            for key, bucket in self._buckets.items():
                # Remove buckets not used in the last hour
                if now - bucket.last_refill > 3600:
                    stale_keys.append(key)
            for key in stale_keys:
                del self._buckets[key]
            if stale_keys:
                logger.debug("ratelimit.cleaned_buckets", count=len(stale_keys))


# Singleton
rate_limiter_registry = RateLimiterRegistry()


# ── Middleware ──


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for token bucket rate limiting.

    Uses request path + client IP as the rate limit key.
    Returns 429 with Retry-After for rate-limited requests.
    """

    SKIP_PATTERNS = (
        "/api/v1/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip rate limiting for health/docs endpoints
        if request.url.path.startswith(self.SKIP_PATTERNS):
            return await call_next(request)

        # Determine rate limit key and limits
        client_ip = request.client.host if request.client else "unknown"
        rps = rate_limiter_registry.get_route_rps(request.url.path)
        burst = rate_limiter_registry.get_route_burst(request.url.path)

        # Bucket per route + IP combo for better isolation
        bucket_key = f"{request.url.path}:{client_ip}"
        bucket = await rate_limiter_registry.get_or_create_bucket(bucket_key, rps, burst)

        allowed, wait = await bucket.consume()

        if not allowed:
            retry_after = math.ceil(wait)
            logger.warning(
                "ratelimit.exceeded",
                path=request.url.path,
                client_ip=client_ip,
                retry_after=retry_after,
                rps=rps,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": 4003,  # QUOTA_EXCEEDED
                        "message": f"Rate limit exceeded. "
                        f"Limit: {rps} req/s. Retry after {retry_after}s.",
                    }
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(rps),
                    "X-RateLimit-Burst": str(burst),
                },
            )

        # Call the next handler
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(rps)
        response.headers["X-RateLimit-Burst"] = str(burst)
        response.headers["X-RateLimit-Remaining"] = str(max(0, int(bucket.tokens)))

        return response


# ── Cleanup task ──


async def rate_limit_cleanup_loop() -> None:
    """Background task to clean up stale rate limit buckets."""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        await rate_limiter_registry.cleanup_stale()
