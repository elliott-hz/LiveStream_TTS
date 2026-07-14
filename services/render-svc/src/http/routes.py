"""
Render Service HTTP routes — FastAPI REST endpoints.

Provides:
  - GET    /api/v1/health              — Health check
  - POST   /api/v1/render              — Non-streaming render (returns frame bytes)
  - POST   /api/v1/predict-lipsync     — Predict blendshape weights
  - GET    /api/v1/gpu-status          — Get mock GPU status
"""

from __future__ import annotations

import base64
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Monorepo path setup
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
RENDER_SVC_ROOT = REPO_ROOT / "services" / "render-svc"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(RENDER_SVC_ROOT))

from libs.common.logging import get_logger

from libs.proto.render.v1 import render_pb2

logger = get_logger(__name__)


# ── Request / Response models ──


class RenderRequest(BaseModel):
    avatar_id: str
    audio_base64: str = ""
    background_id: str = "default"
    width: int = 1920
    height: int = 1080
    fps: int = 30


class RenderResponse(BaseModel):
    request_id: str
    frame_base64: str
    frame_number: int
    is_final: bool


class PredictLipSyncRequest(BaseModel):
    audio_base64: str
    sample_rate: int = 16000
    avatar_id: str = "default"


class PredictLipSyncResponse(BaseModel):
    blendshape_weights: list[float]
    frame_count: int


class GPUStatusResponse(BaseModel):
    device_name: str
    total_memory_mb: int
    used_memory_mb: int
    gpu_utilization_pct: int
    active_streams: int


# ── App Factory ──


def create_http_app(grpc_service: Any) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        grpc_service: An instance of ``RenderGrpcService`` (duck-typed).
    """
    app = FastAPI(
        title="Render Service",
        version="0.1.0",
        description="Digital Human Visual Rendering Service",
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

    # ── Render ──

    @app.post("/api/v1/render", response_model=RenderResponse)
    async def render(data: RenderRequest):
        """Render a single frame for the given avatar."""
        request_id = f"http-ren-{int(time.time() * 1000)}"

        audio_data = base64.b64decode(data.audio_base64) if data.audio_base64 else b""

        proto_req = render_pb2.RenderRequest(
            request_id=request_id,
            avatar_id=data.avatar_id,
            audio_data=audio_data,
            background_id=data.background_id,
            video_config=render_pb2.VideoConfig(
                width=data.width,
                height=data.height,
                fps=data.fps,
            ),
        )

        # We need a minimal mock context; for HTTP we call the service method
        # by constructing the request ourselves.
        from src.api.grpc_impl import RenderGrpcService

        # Since Render is unary-unary on proto level, we can create a service
        # instance and call the method with a dummy context.

        class DummyContext:
            def set_code(self, code): ...
            def set_details(self, details): ...

        import grpc as grpc_mod

        dummy_ctx = DummyContext()
        # Use the existing grpc_service if provided, else create one
        svc = grpc_service if grpc_service is not None else RenderGrpcService()

        # Call the underlying render logic directly (bypass context gRPC checks)
        from src.renderer.compositor import compose_frame

        frame_bytes = compose_frame(
            avatar_id=data.avatar_id,
            frame_number=0,
            width=data.width,
            height=data.height,
            fps=data.fps,
            background_id=data.background_id,
        )

        return RenderResponse(
            request_id=request_id,
            frame_base64=base64.b64encode(frame_bytes).decode(),
            frame_number=0,
            is_final=True,
        )

    # ── Predict LipSync ──

    @app.post("/api/v1/predict-lipsync", response_model=PredictLipSyncResponse)
    async def predict_lipsync(data: PredictLipSyncRequest):
        """Predict blendshape weights from audio."""
        audio_data = base64.b64decode(data.audio_base64)

        from src.renderer.lipsync import predict_blendshapes

        weights, frame_count = predict_blendshapes(
            audio_data=audio_data,
            sample_rate=data.sample_rate,
            avatar_id=data.avatar_id,
        )

        return PredictLipSyncResponse(
            blendshape_weights=weights.flatten().tolist(),
            frame_count=frame_count,
        )

    # ── GPU Status ──

    @app.get("/api/v1/gpu-status", response_model=GPUStatusResponse)
    async def gpu_status():
        """Get mock GPU status."""
        svc = grpc_service if grpc_service is not None else RenderGrpcService()
        status = svc.gpu.get_status()
        return GPUStatusResponse(
            device_name=status.device_name,
            total_memory_mb=status.total_memory_mb,
            used_memory_mb=status.used_memory_mb,
            gpu_utilization_pct=status.gpu_utilization_pct,
            active_streams=status.active_streams,
        )

    return app
