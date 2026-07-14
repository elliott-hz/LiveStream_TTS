"""Live-mgr-svc entry point.

Starts both gRPC (port 50051) and HTTP (port 8080) servers concurrently
using asyncio.

Usage:
    python -m services.live_mgr_svc.src.main
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ── Monorepo bootstrap: add repo root + proto dir to sys.path ──
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))                      # for libs.common.*, services.*
sys.path.insert(0, str(_REPO_ROOT / "libs" / "proto"))    # for generated proto imports

from fastapi import FastAPI
import uvicorn

from libs.common.logging import get_logger, setup_logging
from libs.common.grpc_utils import create_grpc_server
from libs.db import Database
from libs.kafka import KafkaClient
from services.live_mgr_svc.src.config import LiveMgrConfig
from services.live_mgr_svc.src.services.live_room_service import LiveRoomService
from services.live_mgr_svc.src.services.playlist_service import PlaylistService
from services.live_mgr_svc.src.api.grpc_impl import LiveManagerServicer
from services.live_mgr_svc.src.http.routes import create_router

# Proto stubs (checked in under libs/proto/)
from libs.proto.live_mgr.v1 import live_mgr_pb2_grpc

logger = get_logger(__name__)


async def main() -> None:
    """Initialise all components and start both servers."""
    # ── Configuration & logging ──
    config = LiveMgrConfig()
    setup_logging(service_name="live-mgr-svc", level=config.get("LOG_LEVEL", "INFO"))
    logger.info(
        "Starting live-mgr-svc",
        env=config.env,
        grpc_port=config.grpc_port,
        http_port=config.http_port,
    )

    # ── Database ──
    db = Database(config)
    await db.connect()
    logger.info("Database connected", dsn_redacted=_redact_dsn(config.db_dsn))

    # ── Kafka ──
    kafka = KafkaClient(config)
    await kafka.connect()
    logger.info("Kafka connected", bootstrap_servers=config.kafka_bootstrap_servers)

    # ── Service layer ──
    live_room_service = LiveRoomService(db.session, config, kafka_client=kafka)
    playlist_service = PlaylistService(db.session, config)

    # ── gRPC server ──
    grpc_server = create_grpc_server(
        service_name="live-mgr-svc",
        port=config.grpc_port,
        max_workers=config.grpc_max_workers,
    )
    servicer = LiveManagerServicer(live_room_service, playlist_service)
    live_mgr_pb2_grpc.add_LiveManagerServiceServicer_to_server(servicer, grpc_server)
    logger.info("gRPC server configured", port=config.grpc_port)

    # ── HTTP (FastAPI) server ──
    app = FastAPI(
        title="Live Manager Service",
        version="0.1.0",
        description="Live Room management microservice for the Digital Human Livestream Platform",
    )
    router = create_router(live_room_service, playlist_service)
    app.include_router(router)

    http_config = uvicorn.Config(
        app=app,
        host=config.http_host,
        port=config.http_port,
        log_level=config.get("LOG_LEVEL", "info").lower(),
        access_log=True,
    )
    http_server = uvicorn.Server(http_config)

    logger.info("HTTP server configured", host=config.http_host, port=config.http_port)

    # ── Run both servers ──
    try:
        await asyncio.gather(
            grpc_server.start(),
            http_server.serve(),
        )
    except asyncio.CancelledError:
        logger.info("Servers shutting down (CancelledError)")
    except Exception:
        logger.exception("Unexpected error in main loop")
    finally:
        logger.info("Shutting down ...")
        await grpc_server.stop(grace=5)
        await kafka.disconnect()
        await db.disconnect()
        logger.info("Shutdown complete")


def _redact_dsn(dsn: str) -> str:
    """Redact the password in a PostgreSQL DSN for logging."""
    if "@" in dsn:
        before, after = dsn.split("@", 1)
        if ":" in before:
            before = before.split(":")[0] + ":****"
        return f"{before}@{after}"
    return dsn


if __name__ == "__main__":
    asyncio.run(main())
