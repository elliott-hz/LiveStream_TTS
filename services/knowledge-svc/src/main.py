"""
Entrypoint for knowledge-svc.

Starts both:
  1. gRPC server (port from config, default 50051)
  2. HTTP / health server (port from config, default 8008)

Usage:
    python services/knowledge-svc/src/main.py
"""

import asyncio
import sys
from pathlib import Path

# ── Path setup ──
# Priority: proto > modules > svc_root > src > repo_root
_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_SRC_DIR = str(Path(__file__).resolve().parent)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

_SVC_ROOT = str(Path(__file__).resolve().parent.parent)
if _SVC_ROOT not in sys.path:
    sys.path.insert(0, _SVC_ROOT)

_MODULES_DIR = str(Path(__file__).resolve().parent.parent / "modules")
if _MODULES_DIR not in sys.path:
    sys.path.insert(0, _MODULES_DIR)

_LIBS_PROTO = str(Path(_REPO_ROOT) / "libs" / "proto")
if _LIBS_PROTO not in sys.path:
    sys.path.insert(0, _LIBS_PROTO)

from fastapi import FastAPI
import uvicorn

from libs.common.grpc_utils import create_grpc_server
from libs.common.logging import get_logger, setup_logging
from libs.db import Database

from config import config, GRPC_PORT, HTTP_PORT, HTTP_HOST
from api.grpc_impl import KnowledgeServiceServicer
from http_routes.routes import router, configure_routes

from knowledge.v1 import knowledge_pb2_grpc as pb_grpc

logger = get_logger(__name__)


async def serve() -> None:
    """Start gRPC + HTTP servers and wait for shutdown."""
    setup_logging(service_name="knowledge-svc", json_format=config.env != "dev")

    # ── Database ──
    db = Database(config)
    await db.connect()
    logger.info("db.connected", dsn=db.dsn)

    # ── HTTP server (FastAPI) ──
    app = FastAPI(
        title="Knowledge Service",
        version="0.1.0",
        description="Digital Human Livestream Platform — Knowledge Base Management Service",
    )

    configure_routes(db.session)
    app.include_router(router)

    # ── gRPC server ──
    grpc_server = create_grpc_server(
        service_name="knowledge-svc",
        port=GRPC_PORT,
    )

    async def _make_service() -> "KnowledgeService":
        from src.services.knowledge_service import KnowledgeService as KS
        return KS(db=db.session())

    servicer = KnowledgeServiceServicer(knowledge_service_factory=_make_service)
    pb_grpc.add_KnowledgeServiceServicer_to_server(servicer, grpc_server)

    # ── Start ──
    logger.info(
        "server.starting",
        grpc_port=GRPC_PORT,
        http_port=HTTP_PORT,
    )

    async def run_grpc() -> None:
        await grpc_server.start()
        logger.info("grpc.server.started", port=GRPC_PORT)
        await grpc_server.wait_for_termination()

    grpc_task = asyncio.create_task(run_grpc())

    http_config = uvicorn.Config(
        app,
        host=HTTP_HOST,
        port=HTTP_PORT,
        log_level="info" if config.env != "dev" else "debug",
        reload=config.env == "dev",
    )
    server = uvicorn.Server(http_config)
    await server.serve()

    # Clean shutdown
    logger.info("server.shutting_down")
    await grpc_server.stop(grace=5)
    grpc_task.cancel()
    await db.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        logger.info("server.stopped")
