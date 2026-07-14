"""
TTS Service Entry Point

Refactored from POC — now runs as an independent microservice
within the monorepo. Starts a gRPC server (TTSService) and an
HTTP server (FastAPI health / REST / WebSocket).

Usage:
    python -m services.tts_svc.src.main           # via repo-root module
    python services/tts-svc/src/main.py           # direct
    ENV=prod python services/tts-svc/src/main.py  # prod config
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

# Add repo root to path for monorepo imports (must be first)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
TTS_SVC_ROOT = REPO_ROOT / "services" / "tts-svc"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TTS_SVC_ROOT))

from modules.engine.cloud_tts_client import CloudTTSConfig
from src.config import TTSConfig
from src.grpc_service import TTSGrpcService, VoiceStore
from src.http_server import create_http_app

from libs.common.logging import get_logger, setup_logging


async def main() -> None:
    """Start the TTS service (gRPC + HTTP)."""
    config = TTSConfig()
    setup_logging("tts-svc", level=config.get("LOG_LEVEL", "INFO"))

    logger = get_logger(__name__)
    logger.info("tts_svc.starting", version="0.2.0", env=config.env)

    # ── Shared state ──
    voice_store = VoiceStore()

    # ── Cloud TTS config (optional, only used when TTS_BACKEND=cloud) ──
    cloud_config: CloudTTSConfig | None = None
    if config.tts_backend == "cloud":
        cloud_config = CloudTTSConfig(
            access_key_id=config.aliyun_access_key_id,
            access_key_secret=config.aliyun_access_key_secret,
            app_key=config.aliyun_nls_app_key,
            endpoint=config.aliyun_nls_endpoint,
            voice=config.cloud_voice_name,
            sample_rate=16000,
            speech_rate=config.cloud_speech_rate,
            volume=config.cloud_volume,
        )
        logger.info("tts_svc.cloud_backend", voice=cloud_config.voice, endpoint=cloud_config.endpoint)

    # ── gRPC Service ──
    from libs.common.grpc_utils import create_grpc_server
    from libs.proto.tts.v1 import tts_pb2_grpc

    grpc_service = TTSGrpcService(voice_store=voice_store, cloud_config=cloud_config)
    grpc_server = create_grpc_server(
        service_name="tts-svc",
        port=config.grpc_port,
        max_workers=config.max_concurrent_synthesis,
    )
    tts_pb2_grpc.add_TTSServiceServicer_to_server(grpc_service, grpc_server)
    await grpc_server.start()
    logger.info("grpc.server.started", port=config.grpc_port)

    # ── HTTP Server (FastAPI) ──
    import uvicorn

    http_app = create_http_app(grpc_service, voice_store, cloud_config=cloud_config)
    http_config = uvicorn.Config(
        http_app,
        host=config.get("HTTP_HOST", "0.0.0.0"),
        port=config.http_port,
        log_level=config.get("LOG_LEVEL", "info").lower(),
    )
    http_server = uvicorn.Server(http_config)

    logger.info(
        "tts_svc.ready",
        grpc_port=config.grpc_port,
        http_port=config.http_port,
        max_concurrent=config.max_concurrent_synthesis,
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
        logger.info("tts_svc.shutdown")
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
