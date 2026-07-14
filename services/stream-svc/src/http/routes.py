"""
Stream Service HTTP routes — FastAPI REST endpoints.

Provides:
  - GET    /api/v1/health              — Health check
  - POST   /api/v1/stream/start        — Start push stream
  - POST   /api/v1/stream/stop         — Stop push stream
  - GET    /api/v1/stream/{session_id} — Get push status
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Monorepo path setup
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
STREAM_SVC_ROOT = REPO_ROOT / "services" / "stream-svc"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(STREAM_SVC_ROOT))

from libs.common.logging import get_logger

logger = get_logger(__name__)


# ── Request / Response models ──


class StartPushRequest(BaseModel):
    live_room_id: str


class StartPushResponse(BaseModel):
    session_id: str
    live_room_id: str
    rtmp_url: str
    stream_key: str
    status: str


class StopPushRequest(BaseModel):
    session_id: str


class PushStatusResponse(BaseModel):
    session_id: str
    status: str
    fps: int
    bitrate_kbps: int
    uptime_seconds: int
    dropped_frames: int
    health_score: float


# ── App Factory ──


def create_http_app(grpc_service: Any) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        grpc_service: An instance of ``StreamGrpcService`` (duck-typed).
    """
    app = FastAPI(
        title="Stream Service",
        version="0.1.0",
        description="Digital Human Live Stream Push Service",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _start_time = time.time()

    # ── Health ──

    @app.get("/api/v1/health")
    async def health():
        return {
            "status": "healthy",
            "version": "0.1.0",
            "uptime_seconds": int(time.time() - _start_time),
        }

    # ── Start Push ──

    @app.post("/api/v1/stream/start", response_model=StartPushResponse)
    async def start_push(data: StartPushRequest):
        """Start a stream push session."""
        if not data.live_room_id:
            raise HTTPException(status_code=400, detail="live_room_id is required")

        session = grpc_service.push_manager.create_session(
            live_room_id=data.live_room_id,
            rtmp_base_url=grpc_service.config.rtmp_base_url,
        )

        return StartPushResponse(
            session_id=session.session_id,
            live_room_id=session.live_room_id,
            rtmp_url=session.rtmp_url,
            stream_key=session.stream_key,
            status=session.status.name,
        )

    # ── Stop Push ──

    @app.post("/api/v1/stream/stop")
    async def stop_push(data: StopPushRequest):
        """Stop a stream push session."""
        ok = grpc_service.push_manager.stop_session(data.session_id)
        if not ok:
            raise HTTPException(
                status_code=404,
                detail=f"session not found: {data.session_id}",
            )
        return {"session_id": data.session_id, "status": "stopped"}

    # ── Get Push Status ──

    @app.get("/api/v1/stream/{session_id}", response_model=PushStatusResponse)
    async def get_push_status(session_id: str):
        """Get push status for a session."""
        status_data = grpc_service.push_manager.get_status(session_id)
        if not status_data:
            raise HTTPException(
                status_code=404,
                detail=f"session not found: {session_id}",
            )
        return PushStatusResponse(
            session_id=status_data["session_id"],
            status=status_data["status"].name,
            fps=status_data["fps"],
            bitrate_kbps=status_data["bitrate_kbps"],
            uptime_seconds=status_data["uptime_seconds"],
            dropped_frames=status_data["dropped_frames"],
            health_score=status_data["health_score"],
        )

    return app
