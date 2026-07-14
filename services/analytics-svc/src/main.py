"""
Entrypoint for analytics-svc.

Starts both:
  1. gRPC server (port from config, default 50051)
  2. HTTP / health server (port from config, default 8014)
"""

import asyncio
import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_SRC_DIR = str(Path(__file__).resolve().parent)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

_LIBS_PROTO = str(Path(_REPO_ROOT) / "libs" / "proto")
if _LIBS_PROTO not in sys.path:
    sys.path.insert(0, _LIBS_PROTO)

import uvicorn
from fastapi import FastAPI

from libs.common.grpc_utils import create_grpc_server
from libs.common.logging import get_logger, setup_logging
from libs.db import Database

from config import config, GRPC_PORT, HTTP_PORT, HTTP_HOST
from api.grpc_impl import AnalyticsServiceServicer
from http.routes import router, configure_routes

from analytics.v1 import analytics_pb2_grpc as pb_grpc

logger = get_logger(__name__)


async def serve() -> None:
    setup_logging(service_name="analytics-svc", json_format=config.env != "dev")

    db = Database(config)
    await db.connect()
    logger.info("db.connected", dsn=db.dsn)

    app = FastAPI(
        title="Analytics Service",
        version="0.1.0",
        description="Live Data Analytics Service",
    )

    configure_routes(db.session)
    app.include_router(router)

    def _make_svc():
        from services.analytics_service import AnalyticsService
        return AnalyticsService(db=db.session())

    grpc_server = create_grpc_server(
        service_name="analytics-svc",
        port=GRPC_PORT,
    )

    servicer = AnalyticsServiceServicer(service_factory=_make_svc)
    pb_grpc.add_AnalyticsServiceServicer_to_server(servicer, grpc_server)

    logger.info("server.starting", grpc_port=GRPC_PORT, http_port=HTTP_PORT)

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

    logger.info("server.shutting_down")
    await grpc_server.stop(grace=5)
    grpc_task.cancel()
    await db.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        logger.info("server.stopped")
