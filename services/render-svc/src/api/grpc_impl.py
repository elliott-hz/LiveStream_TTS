"""
Render gRPC Service Implementation — RenderServiceServicer.

Implements all RPCs from libs/proto/render/v1/render.proto:
  - Render             — Accept audio + avatar_id -> generate mock video frames
  - PredictLipSync     — Return random blendshape weights (placeholder)
  - GetGPUStatus       — Return mock GPU info
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator

import grpc
import numpy as np

# Monorepo path setup
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
RENDER_SVC_ROOT = REPO_ROOT / "services" / "render-svc"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(RENDER_SVC_ROOT))

from libs.common.errors import ErrorCode, Domain, AppError, not_found, internal
from libs.common.logging import get_logger

from libs.proto.render.v1 import render_pb2, render_pb2_grpc
from libs.proto.common.v1 import common_pb2

from src.renderer.lipsync import predict_blendshapes
from src.renderer.compositor import compose_frame
from src.renderer.overlays import (
    OverlayDefinition,
    OverlayType,
    Position,
    proto_overlay_to_definition,
)
from src.config import RenderConfig

logger = get_logger(__name__)


# ── GPU Status (mock) ──


class GPUManager:
    """Mock GPU resource manager.

    In production this would query nvidia-smi / CUDA runtime.
    """

    def __init__(self, config: RenderConfig) -> None:
        self.config = config
        self._start_time = time.time()
        self._active_streams: set[str] = set()

    def get_status(self) -> render_pb2.GPUStatus:
        """Return mock GPU status."""
        return render_pb2.GPUStatus(
            device_name=f"Mock NVIDIA L40S (GPU {self.config.gpu_device})",
            total_memory_mb=46080,
            used_memory_mb=int(46080 * self.config.gpu_memory_fraction * 0.6),
            gpu_utilization_pct=42,
            active_streams=len(self._active_streams),
        )

    def register_stream(self, session_id: str) -> None:
        self._active_streams.add(session_id)

    def unregister_stream(self, session_id: str) -> None:
        self._active_streams.discard(session_id)


# ── gRPC Servicer ──


class RenderGrpcService(render_pb2_grpc.RenderServiceServicer):
    """gRPC servicer for the RenderService.

    Provides mock implementations for:
      - Render (unary)
      - PredictLipSync (unary)
      - GetGPUStatus (unary)
    """

    def __init__(self, config: RenderConfig | None = None) -> None:
        self.config = config or RenderConfig()
        self.gpu = GPUManager(self.config)
        self._start_time = time.time()

    # ── Render ──

    async def Render(
        self,
        request: render_pb2.RenderRequest,
        context: grpc.aio.ServicerContext,
    ) -> render_pb2.RenderResponse:
        """Accept audio + avatar_id -> generate mock video frames.

        In production this would run the full rendering pipeline:
          Wav2Lip -> blendshapes -> FFmpeg compositing -> encoded frame.
        Here we return a small dummy byte payload.
        """
        request_id = request.request_id or f"ren-{uuid.uuid4().hex[:12]}"
        logger.info(
            "grpc.render.start",
            request_id=request_id,
            avatar_id=request.avatar_id,
            audio_bytes=len(request.audio_data),
            overlays=len(request.overlays),
        )

        if not request.avatar_id:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("avatar_id is required")
            return render_pb2.RenderResponse(
                request_id=request_id,
                is_final=True,
            )

        # Build overlay definitions from proto
        overlay_defs = [
            proto_overlay_to_definition(o) for o in request.overlays
        ]

        # Compose a single mock frame
        video_config = request.video_config
        frame_bytes = compose_frame(
            avatar_id=request.avatar_id,
            frame_number=0,
            width=video_config.width or 1920,
            height=video_config.height or 1080,
            fps=video_config.fps or 30,
            background_id=request.background_id or "default",
            overlays=overlay_defs,
        )

        self.gpu.register_stream(request_id)

        logger.info(
            "grpc.render.complete",
            request_id=request_id,
            frame_bytes=len(frame_bytes),
        )

        return render_pb2.RenderResponse(
            request_id=request_id,
            video_frame=frame_bytes,
            frame_number=0,
            is_final=True,
        )

    # ── PredictLipSync ──

    async def PredictLipSync(
        self,
        request: render_pb2.PredictLipSyncRequest,
        context: grpc.aio.ServicerContext,
    ) -> render_pb2.PredictLipSyncResponse:
        """Return random blendshape weights (placeholder)."""
        request_id = f"lipsync-{uuid.uuid4().hex[:8]}"
        logger.info(
            "grpc.predict_lipsync.start",
            audio_bytes=len(request.audio_data),
            avatar_id=request.avatar_id or "unknown",
        )

        if not request.audio_data:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("audio_data is required")
            return render_pb2.PredictLipSyncResponse(
                blendshape_weights=[],
                frame_count=0,
            )

        weights_matrix, frame_count = predict_blendshapes(
            audio_data=request.audio_data,
            sample_rate=request.sample_rate,
            avatar_id=request.avatar_id,
        )

        # Flatten the weights matrix into a float list
        flat_weights: list[float] = weights_matrix.flatten().tolist()

        logger.info(
            "grpc.predict_lipsync.complete",
            frame_count=frame_count,
            weights_len=len(flat_weights),
        )

        return render_pb2.PredictLipSyncResponse(
            blendshape_weights=flat_weights,
            frame_count=frame_count,
        )

    # ── GetGPUStatus ──

    async def GetGPUStatus(
        self,
        request: render_pb2.GetGPUStatusRequest,
        context: grpc.aio.ServicerContext,
    ) -> render_pb2.GPUStatus:
        """Return mock GPU info."""
        status = self.gpu.get_status()
        logger.debug("grpc.gpu_status", device=status.device_name)
        return status
