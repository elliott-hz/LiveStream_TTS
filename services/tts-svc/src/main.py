"""
TTS Service Entry Point

Refactored from POC src/main.py — now runs as an independent microservice
within the monorepo. Provides gRPC + WebSocket interfaces for streaming TTS.
"""

import asyncio
import sys
from pathlib import Path

# Add repo root to path for monorepo imports
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from libs.common.config import ServiceConfig
from libs.common.logging import setup_logging, get_logger


async def main():
    config = ServiceConfig("tts-svc")
    setup_logging("tts-svc", level=config.get("LOG_LEVEL", "INFO"))

    logger = get_logger(__name__)
    logger.info("tts_svc.starting", version="0.1.0", env=config.env)

    # TODO: Start gRPC server + WebSocket server (Sprint 1-2)
    logger.info("tts_svc.ready")


if __name__ == "__main__":
    asyncio.run(main())
