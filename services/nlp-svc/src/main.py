"""
NLP Service — gRPC + HTTP Entry Point.

Combines:
  - Async gRPC server for internal microservice communication
  - FastAPI HTTP server for external REST APIs (health, analyze, check-sensitive)

Usage:
    python -m services.nlp-svc.src.main
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ── Monorepo path setup ──
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Add service src directory for src. prefix imports
_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from grpc import aio as grpc_aio

from libs.common.grpc_utils import create_grpc_server
from libs.common.logging import get_logger, setup_logging

from .api.grpc_impl import NLPServiceServicerImpl, add_NLPServiceServicer_to_server
from .config import config
from .http.routes import router as http_router

logger = get_logger(__name__)


class NLPServiceRunner:
    """Manages gRPC + HTTP server lifecycle."""

    def __init__(self) -> None:
        self.grpc_server: grpc_aio.Server | None = None
        self.http_app: FastAPI | None = None

    def create_http_app(self) -> FastAPI:
        """Create the FastAPI application with all routes."""
        app = FastAPI(
            title="NLP Service",
            description="Natural Language Processing Service for the Digital Human "
            "Livestream Platform. Provides intent classification, sentiment analysis, "
            "sensitive word detection, entity extraction, and text rewriting.",
            version="0.1.0",
            lifespan=self._lifespan,
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json",
        )

        # CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Include HTTP routes
        app.include_router(http_router)

        # Root endpoint
        @app.get("/")
        async def root():
            return {
                "service": "nlp-svc",
                "version": "0.1.0",
                "docs": "/docs",
                "health": "/api/v1/health",
            }

        self.http_app = app
        return app

    async def start_grpc(self) -> grpc_aio.Server:
        """Start the gRPC server."""
        self.grpc_server = create_grpc_server(
            service_name="nlp-svc",
            port=config.grpc_port,
            max_workers=config.grpc_max_workers,
        )

        # Register NLP service
        add_NLPServiceServicer_to_server(
            NLPServiceServicerImpl(),
            self.grpc_server,
        )

        await self.grpc_server.start()
        logger.info(
            "grpc.server.started",
            port=config.grpc_port,
            max_workers=config.grpc_max_workers,
        )
        return self.grpc_server

    async def stop_grpc(self) -> None:
        """Stop the gRPC server gracefully."""
        if self.grpc_server:
            await self.grpc_server.stop(grace=5)
            logger.info("grpc.server.stopped")

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        """FastAPI lifespan: starts gRPC server on startup, stops on shutdown."""
        # Startup
        logger.info(
            "nlp-svc.starting",
            http_port=config.http_port,
            grpc_port=config.grpc_port,
            env=config.env,
        )
        grpc_task = asyncio.create_task(self.start_grpc())

        yield

        # Shutdown
        logger.info("nlp-svc.shutting_down")
        await self.stop_grpc()
        grpc_task.cancel()
        try:
            await grpc_task
        except asyncio.CancelledError:
            pass
        logger.info("nlp-svc.shutdown_complete")


# ── Runner instance ──

runner = NLPServiceRunner()
app = runner.create_http_app()


# ── Entry point ──

def main() -> None:
    """Run the NLP service with both gRPC and HTTP servers."""
    setup_logging(
        service_name="nlp-svc",
        level=config.log_level,
        json_format=config.log_json,
    )

    logger.info(
        "nlp-svc.main.starting",
        http=f"{config.http_host}:{config.http_port}",
        grpc=f":{config.grpc_port}",
    )

    uvicorn.run(
        "services.nlp-svc.src.main:app",
        host=config.http_host,
        port=config.http_port,
        reload=config.env == "dev",
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    main()
