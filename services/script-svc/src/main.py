"""
Script Service Entry Point

Provides gRPC + HTTP interfaces for script CRUD, AI generation,
version management, and template listing.

Usage:
    python -m services.script-svc.src.main
    # or via installed package:
    script-svc
"""

import asyncio
import sys
from pathlib import Path

# ── Monorepo import path ──
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Also add the script-svc directory so modules/ can be imported
SCRIPT_SVC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_SVC_DIR))

import grpc
from fastapi import FastAPI
from grpc import aio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from uvicorn import Config, Server

from libs.common.config import ServiceConfig
from libs.common.grpc_utils import create_grpc_server
from libs.common.logging import setup_logging, get_logger
from libs.db import Database

from modules.script.v1 import script_pb2_grpc
from src.api.grpc_impl import ScriptServiceServicer
from src.config import ScriptConfig
from src.http.routes import router, TEMPLATES_ROUTER

logger = get_logger(__name__)


def create_fastapi_app(config: ScriptConfig) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Script Service",
        description="AI Script Generation, Editing, Versioning, Templates",
        version="0.1.0",
    )

    # Include routers
    app.include_router(router)
    app.include_router(TEMPLATES_ROUTER)

    # Health check
    @app.get("/api/v1/health")
    async def health():
        return {"status": "healthy", "service": "script-svc"}

    return app


async def run_grpc_server(config: ScriptConfig, db: Database) -> aio.Server:
    """Start the gRPC server for ScriptService."""
    server = create_grpc_server(
        service_name="script-svc",
        port=config.grpc_port,
        max_workers=config.get_int("GRPC_MAX_WORKERS", 20),
    )

    # Create a session for the servicer
    async with db.session() as session:
        servicer = ScriptServiceServicer(session, config)
        script_pb2_grpc.add_ScriptServiceServicer_to_server(servicer, server)

    await server.start()
    logger.info("grpc.server_started", port=config.grpc_port)
    return server


async def main():
    config = ScriptConfig()
    setup_logging("script-svc", level=config.log_level)

    logger.info("script_svc.starting", version="0.1.0", env=config.env)

    # ── Database ──
    db = Database(config)
    await db.connect()
    logger.info("database.connected")

    # ── gRPC Server ──
    grpc_server = await run_grpc_server(config, db)

    # ── HTTP Server (FastAPI) ──
    app = create_fastapi_app(config)
    http_config = Config(
        app=app,
        host=config.get("HTTP_HOST", "0.0.0.0"),
        port=config.http_port,
        log_level=config.log_level.lower(),
    )
    http_server = Server(http_config)

    logger.info("script_svc.ready", grpc_port=config.grpc_port, http_port=config.http_port)

    try:
        # Run both servers concurrently
        await asyncio.gather(
            http_server.serve(),
            _grpc_serve_forever(grpc_server),
        )
    except asyncio.CancelledError:
        logger.info("script_svc.shutting_down")
    finally:
        await grpc_server.stop(grace=5)
        await db.disconnect()
        logger.info("script_svc.stopped")


async def _grpc_serve_forever(server: aio.Server) -> None:
    """Keep the gRPC server running until cancelled."""
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(main())
