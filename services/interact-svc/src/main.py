"""
Interact Service — Main Entry Point.

Runs both:
  - FastAPI HTTP server (port 8080) for REST endpoints
  - Async gRPC server (port 50051) for InteractionService RPCs

Usage:
    python -m services.interact-svc.src.main
    # or
    uvicorn services.interact-svc.src.main:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Monorepo path setup ──
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_LIBS_PROTO = _REPO_ROOT / "libs" / "proto"
_SVC_ROOT = Path(__file__).resolve().parent.parent
for p in [str(_REPO_ROOT), str(_LIBS_PROTO), str(_SVC_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from libs.common.grpc_utils import create_grpc_server
from libs.common.logging import get_logger, setup_logging
from libs.kafka import KafkaClient

from src.api.grpc_impl import InteractionServiceServicer
from src.config import config
from src.http_routes import interact_router
from src.http_routes.routes import init_routes
from src.services import InteractionService

logger = get_logger(__name__)

# ── Global service instances ──

_service: InteractionService | None = None
_kafka: KafkaClient | None = None
_grpc_server: Any | None = None


def get_service() -> InteractionService:
    """Get the singleton InteractionService instance."""
    global _service
    if _service is None:
        _service = InteractionService()
    return _service


# ── Application lifecycle ──


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan context manager for startup/shutdown."""
    global _kafka, _grpc_server

    logger.info(
        "interact.starting",
        http_host=config.http_host,
        http_port=config.http_port,
        grpc_port=config.grpc_port,
        env=config.env,
    )

    # Initialize service
    service = get_service()

    # Initialize Kafka client
    _kafka = KafkaClient(config)
    try:
        await _kafka.connect()
        logger.info("kafka.connected")
    except Exception as e:
        logger.warning("kafka.connect_failed", error=str(e))

    # Inject service into HTTP routes
    init_routes(service)

    # Start gRPC server (in-process with FastAPI)
    grpc_service = InteractionServiceServicer(service)
    _grpc_server = await _start_grpc_server(grpc_service)

    logger.info("interact.started")

    yield  # Application runs here

    # ── Shutdown ──
    logger.info("interact.shutting_down")

    if _grpc_server:
        await _grpc_server.stop(grace=5)

    if _kafka:
        await _kafka.disconnect()

    logger.info("interact.shutdown_complete")


# ── Application factory ──


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    setup_logging(
        service_name="interact-svc",
        level=config.log_level,
        json_format=config.log_json,
    )

    app = FastAPI(
        title="Digital Human Livestream — Interaction Service",
        description="Real-time Interaction Pipeline for the Digital Human Livestream Platform. "
        "Handles danmaku processing, session management, channel routing, "
        "and AI text moderator actions.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── CORS ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ──
    app.include_router(interact_router)

    # ── Root ──
    @app.get("/")
    async def root():
        return {
            "service": "interact-svc",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


# ── gRPC server ──


async def _start_grpc_server(servicer: InteractionServiceServicer) -> Any:
    """Start the async gRPC server in the background."""
    from grpc import aio as grpc_aio

    from libs.proto.interact.v1 import interact_pb2_grpc

    server = create_grpc_server(
        service_name="interact-svc",
        port=config.grpc_port,
        max_workers=10,
    )
    interact_pb2_grpc.add_InteractionServiceServicer_to_server(servicer, server)

    # Start gRPC server (non-blocking, async)
    logger.info("grpc.starting", port=config.grpc_port)
    await server.start()
    logger.info("grpc.started", port=config.grpc_port)

    return server


# ── Application instance ──

app = create_app()


# ── Entry point ──

def main() -> None:
    """Run the interaction service (HTTP + gRPC) using Uvicorn."""
    uvicorn.run(
        "services.interact-svc.src.main:app",
        host=config.http_host,
        port=config.http_port,
        reload=config.env == "dev",
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    main()
