"""User-svc entry point.

Starts both gRPC (port 50051) and HTTP (port 8080) servers concurrently
using asyncio.

Usage:
    python -m services.user-svc.src.main
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ── Monorepo bootstrap: add repo root + proto dir to sys.path ──
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))                      # for libs.common.*, services.*
sys.path.insert(0, str(_REPO_ROOT / "libs" / "proto"))    # for generated proto imports (common.v1, user.v1)

from fastapi import FastAPI
import uvicorn

from libs.common.logging import get_logger, setup_logging
from libs.common.grpc_utils import create_grpc_server
from libs.db import Database
from services.user_svc.src.config import UserServiceConfig
from services.user_svc.src.services.auth_service import AuthService
from services.user_svc.src.services.user_service import UserService
from services.user_svc.src.api.grpc_impl import UserServiceServicer
from services.user_svc.src.http.routes import create_router

# Proto stubs (checked in under libs/proto/)
from libs.proto.user.v1 import user_pb2_grpc

logger = get_logger(__name__)


async def main() -> None:
    """Initialise all components and start both servers."""
    # ── Configuration & logging ──
    config = UserServiceConfig()
    setup_logging(service_name="user-svc", level=config.get("LOG_LEVEL", "INFO"))
    logger.info("Starting user-svc", env=config.env, grpc_port=config.grpc_port, http_port=config.http_port)

    # ── Database ──
    db = Database(config)
    await db.connect()
    logger.info("Database connected", dsn_redacted=_redact_dsn(config.db_dsn))

    # ── Service layer ──
    auth_service = AuthService(db.session, config)
    user_service = UserService(db.session, config)

    # ── gRPC server ──
    grpc_server = create_grpc_server(
        service_name="user-svc",
        port=config.grpc_port,
        max_workers=config.grpc_max_workers,
    )
    servicer = UserServiceServicer(auth_service, user_service)
    user_pb2_grpc.add_UserServiceServicer_to_server(servicer, grpc_server)
    logger.info("gRPC server configured", port=config.grpc_port)

    # ── HTTP (FastAPI) server ──
    app = FastAPI(
        title="User Service",
        version="0.1.0",
        description="User & Auth microservice for the Digital Human Livestream Platform",
    )
    router = create_router(auth_service, user_service)
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
