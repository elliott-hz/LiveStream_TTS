"""
Entrypoint for product-svc.

Starts both:
  1. gRPC server (port from config, default 50051)
  2. HTTP / health server (port from config, default 8003)

Usage:
    python -m services.product_svc.src.main         # (requires symlink or pth)
    python services/product-svc/src/main.py          # direct
"""

import asyncio
import sys
from pathlib import Path

# ── Path setup ──
# Add the repo root so that `from libs.xxx import ...` works.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Add the service `src/` directory so internal modules use short paths:
#   from models.product import Product
#   from services.product_service import ProductService
_SRC_DIR = str(Path(__file__).resolve().parent)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# Add the generated protobuf modules dir so proto imports resolve:
#   from product.v1 import product_pb2  (via modules/product/v1/...)
_MODULES_DIR = str(Path(__file__).resolve().parent.parent / "modules")
if _MODULES_DIR not in sys.path:
    sys.path.insert(0, _MODULES_DIR)

import grpc
from fastapi import FastAPI
import uvicorn

from libs.common.grpc_utils import create_grpc_server
from libs.common.logging import get_logger, setup_logging
from libs.db import Database

from config import config, GRPC_PORT, HTTP_PORT, HTTP_HOST
from api.grpc_impl import ProductServiceServicer
from rest.routes import router, configure_routes

# Generated protobuf modules
from product.v1 import product_pb2_grpc as pb_grpc

logger = get_logger(__name__)


async def serve() -> None:
    """Start gRPC + HTTP servers and wait for shutdown."""
    setup_logging(service_name="product-svc", json_format=config.env != "dev")

    # ── Database ──
    db = Database(config)
    await db.connect()
    logger.info("db.connected", dsn=db.dsn)

    # ── HTTP server (FastAPI) ──
    app = FastAPI(
        title="Product Service",
        version="0.1.0",
        description="Digital Human Livestream Platform — Product Management Service",
    )

    # Wire HTTP routes with DB session factory
    configure_routes(db.session)
    app.include_router(router)

    # ── gRPC server ──
    grpc_server = create_grpc_server(
        service_name="product-svc",
        port=GRPC_PORT,
    )

    # Create a wrapper that provides a new service per RPC call
    # (each call gets its own DB session)
    service_provider = ProductServiceServicer(product_service_factory=lambda: None)

    # Deferred init — we set the factory on the servicer after DB is ready
    async def _make_service() -> "ProductService":
        from services.product_service import ProductService as PS
        return PS(db=db.session())

    servicer = ProductServiceServicer(product_service_factory=_make_service)
    pb_grpc.add_ProductServiceServicer_to_server(servicer, grpc_server)

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

    # Run FastAPI via uvicorn
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
