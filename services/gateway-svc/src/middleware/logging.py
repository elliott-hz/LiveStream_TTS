"""
Request logging middleware for FastAPI.

Logs all requests with: method, path, status_code, duration_ms, user_id.
Injects x-trace-id (UUID v4) for distributed tracing across services.
Uses structlog for structured JSON logging.
"""

from __future__ import annotations

import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from libs.common.logging import get_logger

logger = get_logger(__name__)

# ── Paths to exclude from logging ──

EXCLUDE_PATHS = (
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
)


class LoggingMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for request logging and trace ID injection.

    Injects x-trace-id into request headers and response headers.
    Logs request details including method, path, status, duration, and user.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip logging for docs endpoints (too noisy)
        if request.url.path.startswith(EXCLUDE_PATHS):
            return await call_next(request)

        # Generate or extract trace ID
        trace_id = request.headers.get("x-trace-id")
        if not trace_id:
            trace_id = str(uuid.uuid4())

        # Store trace ID for downstream use
        request.state.trace_id = trace_id

        # Record start time
        start_time = time.monotonic()

        # Call the next handler
        try:
            response = await call_next(request)
        except Exception as exc:
            # Log the error and re-raise
            duration_ms = (time.monotonic() - start_time) * 1000
            user_id = getattr(request.state, "user", None)
            if user_id:
                user_id = user_id.user_id
            logger.error(
                "request.error",
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_ms=round(duration_ms, 2),
                user_id=user_id,
                trace_id=trace_id,
                error=str(exc),
            )
            raise

        # Inject trace ID into response headers
        response.headers["x-trace-id"] = trace_id

        # Calculate duration
        duration_ms = (time.monotonic() - start_time) * 1000

        # Get user ID from request state (if authenticated)
        user_id = None
        if hasattr(request.state, "user"):
            user_obj = request.state.user
            if user_obj:
                user_id = getattr(user_obj, "user_id", None)

        # Log the request
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "query": str(request.url.query) if request.url.query else None,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "user_id": user_id,
            "trace_id": trace_id,
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }

        if response.status_code >= 500:
            logger.error("request.completed", **log_data)
        elif response.status_code >= 400:
            logger.warning("request.completed", **log_data)
        else:
            logger.info("request.completed", **log_data)

        return response
