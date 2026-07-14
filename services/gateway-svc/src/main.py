"""
Gateway Service — FastAPI Application Entry Point.

The API Gateway is the single entry point for all external HTTP/REST
and WebSocket traffic. It handles:
  - JWT authentication
  - Rate limiting (token bucket)
  - Request logging with distributed tracing (x-trace-id)
  - gRPC proxying to downstream microservices
  - WebSocket proxy for TTS streaming

Usage:
    python -m services.gateway-svc.src.main
    # or
    uvicorn services.gateway-svc.src.main:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ── Monorepo path setup ──
# Allows imports like `from libs.common import ...` and `from proto.x.v1 import ...`
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from libs.common.logging import get_logger, setup_logging

from .config import config
from .grpc_client import grpc_manager
from .middleware.auth import AuthMiddleware
from .middleware.logging import LoggingMiddleware
from .middleware.ratelimit import RateLimitMiddleware, rate_limit_cleanup_loop
from .routes.health import router as health_router
from .routes.proxy import router as proxy_router

logger = get_logger(__name__)


# ── Application lifecycle ──


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup/shutdown events."""
    # ── Startup ──
    logger.info(
        "gateway.starting",
        host=config.http_host,
        port=config.http_port,
        env=config.env,
    )

    # Start gRPC client connections to downstream services
    await grpc_manager.start()

    # Start background cleanup tasks
    cleanup_task = asyncio.create_task(rate_limit_cleanup_loop())

    logger.info("gateway.started")

    yield  # Application runs here

    # ── Shutdown ──
    logger.info("gateway.shutting_down")

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    await grpc_manager.stop()

    logger.info("gateway.shutdown_complete")


# ── Application factory ──


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Setup structured logging
    setup_logging(
        service_name="gateway-svc",
        level=config.log_level,
        json_format=config.log_json,
    )

    app = FastAPI(
        title="Digital Human Livestream Gateway",
        description="API Gateway for the Digital Human Livestream Shopping Platform. "
        "Provides authentication, rate limiting, request logging, "
        "and gRPC-to-REST proxying for all downstream microservices.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── CORS ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=config.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-trace-id", "Retry-After", "X-RateLimit-*"],
    )

    # ── Middleware (order matters: first added = outermost) ──
    app.add_middleware(LoggingMiddleware)  # Outermost: log everything
    app.add_middleware(RateLimitMiddleware)  # Rate limit before auth
    app.add_middleware(AuthMiddleware)  # Authenticate before handlers

    # ── Routes ──
    app.include_router(health_router)
    app.include_router(proxy_router)

    # ── Root endpoint ──
    @app.get("/")
    async def root():
        return {
            "service": "gateway-svc",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


# ── Application instance ──

app = create_app()


# ── Entry point ──

def main() -> None:
    """Run the gateway service using Uvicorn."""
    uvicorn.run(
        "services.gateway-svc.src.main:app",
        host=config.http_host,
        port=config.http_port,
        reload=config.env == "dev",
        log_level=config.log_level.lower(),
        ws="websockets",
    )


if __name__ == "__main__":
    main()
