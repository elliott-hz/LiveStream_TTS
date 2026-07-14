"""
Stream Service Entry Point

Starts a gRPC server (StreamService) and an HTTP server (FastAPI
health / REST endpoints).

Usage:
    python -m services.stream-svc.src.main           # via repo-root module
    python services/stream-svc/src/main.py            # direct
    ENV=prod python services/stream-svc/src/main.py   # prod config
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

# Add repo root to path for monorepo imports (must be first)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
STREAM_SVC_ROOT = REPO_ROOT / "services" / "stream-svc"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(STREAM_SVC_ROOT))

from libs.common.config import ServiceConfig
from libs.common.logging import setup_logging, get_logger
from src.config import StreamConfig
from src.api.grpc_impl import StreamGrpcService
from src.http.routes import create_http_app


async def main() -> None:
    """Start the Stream service (gRPC + HTTP)."""
    config = StreamConfig()
    setup_logging("stream-svc", level=config.get("LOG_LEVEL", "INFO"))

    logger = get_logger(__name__)
    logger.info("stream_svc.starting", version="0.1.0", env=config.env)

    # ── Shared state ──
    grpc_service = StreamGrpcService(config=config)

    # ── gRPC Service ──
    from libs.common.grpc_utils import create_grpc_server
    from libs.proto.stream.v1 import stream_pb2_grpc

    grpc_server = create_grpc_server(
        service_name="stream-svc",
        port=config.grpc_port,
        max_workers=config.get_int("GRPC_MAX_WORKERS", 20),
    )
    stream_pb2_grpc.add_StreamServiceServicer_to_server(grpc_service, grpc_server)
    await grpc_server.start()
    logger.info("grpc.server.started", port=config.grpc_port)

    # ── HTTP Server (FastAPI) ──
    import uvicorn

    http_app = create_http_app(grpc_service)
    http_config = uvicorn.Config(
        http_app,
        host=config.get("HTTP_HOST", "0.0.0.0"),
        port=config.http_port,
        log_level=config.get("LOG_LEVEL", "info").lower(),
    )
    http_server = uvicorn.Server(http_config)

    logger.info(
        "stream_svc.ready",
        grpc_port=config.grpc_port,
        http_port=config.http_port,
    )

    try:
        # Run both servers concurrently
        await asyncio.gather(
            http_server.serve(),
            _grpc_serve_forever(grpc_server, logger),
        )
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("stream_svc.shutdown")
        await grpc_server.stop(grace=5)


async def _grpc_serve_forever(
    server: Any,  # grpc.aio.Server
    logger: Any,
) -> None:
    """Keep the gRPC server alive until cancelled."""
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("grpc.server.interrupted")


# Make importable alias for tests
serve = main

if __name__ == "__main__":
    asyncio.run(main())
