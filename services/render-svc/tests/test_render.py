"""
Unit tests for the Render Service (gRPC + HTTP + renderer modules).
"""

from __future__ import annotations

import sys
import math
from pathlib import Path

import pytest
import numpy as np
from httpx import AsyncClient, ASGITransport

# Monorepo path setup
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
RENDER_SVC_ROOT = REPO_ROOT / "services" / "render-svc"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(RENDER_SVC_ROOT))

from src.api.grpc_impl import RenderGrpcService
from src.http.routes import create_http_app
from src.renderer.lipsync import predict_blendshapes, extract_rms, NUM_BLENDSHAPES
from src.renderer.compositor import compose_frame, compose_frames_batch
from src.renderer.overlays import (
    OverlayDefinition,
    OverlayType,
    Position,
    build_default_overlays,
    render_overlay,
)
from libs.proto.render.v1 import render_pb2


# ── Fixtures ──


@pytest.fixture
def grpc_service():
    return RenderGrpcService()


@pytest.fixture
def app(grpc_service):
    return create_http_app(grpc_service)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_context():
    class MockContext:
        def __init__(self):
            self.code = None
            self.details_value = None

        def set_code(self, code):
            self.code = code

        def set_details(self, details):
            self.details_value = details

        async def abort(self, code, details):
            self.code = code
            self.details_value = details
            raise Exception(details)

    return MockContext()


@pytest.fixture
def sample_audio():
    """Generate 1 second of silent PCM16 audio (16000 Hz)."""
    return b"\x00\x00" * 16000  # 1 second of silence


# ── LipSync Tests ──


class TestPredictBlendshapes:
    """Tests for the lipsync blendshape predictor."""

    def test_returns_correct_shape(self, sample_audio):
        weights, frame_count = predict_blendshapes(sample_audio)
        assert weights.shape[1] == NUM_BLENDSHAPES
        assert frame_count > 0
        assert weights.shape[0] == frame_count

    def test_values_in_range(self, sample_audio):
        weights, _ = predict_blendshapes(sample_audio)
        assert weights.min() >= 0.0
        assert weights.max() <= 1.0

    def test_deterministic_same_input(self, sample_audio):
        w1, _ = predict_blendshapes(sample_audio)
        w2, _ = predict_blendshapes(sample_audio)
        assert np.allclose(w1, w2)

    def test_different_audio_different_output(self):
        audio1 = b"\x00\x00" * 16000
        audio2 = b"\x01\x02" * 16000
        w1, _ = predict_blendshapes(audio1)
        w2, _ = predict_blendshapes(audio2)
        assert not np.allclose(w1, w2)

    def test_empty_audio(self):
        weights, frame_count = predict_blendshapes(b"")
        # Should produce at least 1 frame
        assert frame_count >= 1
        assert weights.shape[0] >= 1

    def test_short_audio(self):
        weights, frame_count = predict_blendshapes(b"\x00\x00" * 100)
        assert frame_count >= 1


class TestExtractRMS:
    """Tests for RMS extraction helper."""

    def test_silence_has_low_rms(self):
        silent = b"\x00\x00" * 16000
        rms = extract_rms(silent)
        assert all(v < 0.01 for v in rms)

    def test_loud_audio_higher_rms(self):
        import struct

        samples = [struct.pack("<h", 30000) for _ in range(16000)]
        loud = b"".join(samples)
        rms = extract_rms(loud)
        assert any(v > 0.5 for v in rms)


# ── Compositor Tests ──


class TestComposeFrame:
    """Tests for the frame compositor."""

    def test_returns_bytes(self):
        frame = compose_frame("avatar_001", 0)
        assert isinstance(frame, bytes)
        assert len(frame) > 0

    def test_different_frames_different(self):
        f1 = compose_frame("avatar_001", 0)
        f2 = compose_frame("avatar_001", 1)
        assert f1 != f2

    def test_different_avatars_different(self):
        f1 = compose_frame("avatar_001", 0)
        f2 = compose_frame("avatar_002", 0)
        assert f1 != f2

    def test_with_overlays(self):
        overlays = [
            OverlayDefinition(
                overlay_id="test",
                type=OverlayType.WATERMARK,
                content="test",
                position=Position(x=10, y=10),
            )
        ]
        frame = compose_frame("avatar_001", 0, overlays=overlays)
        assert len(frame) > 0

    def test_custom_resolution(self):
        frame = compose_frame("avatar_001", 0, width=3840, height=2160)
        assert len(frame) > 0

    def test_batch_compose(self):
        frames = compose_frames_batch("avatar_001", 0, 10)
        assert len(frames) > 0
        assert len(frames) > 64 * 10  # At least header * count


# ── Overlays Tests ──


class TestOverlays:
    """Tests for overlay definitions."""

    def test_default_overlays_count(self):
        overlays = build_default_overlays()
        assert len(overlays) == 3

    def test_default_has_watermark(self):
        overlays = build_default_overlays()
        ids = [o.overlay_id for o in overlays]
        assert "watermark" in ids

    def test_render_overlay_returns_bytes(self):
        overlay = OverlayDefinition(
            overlay_id="test",
            type=OverlayType.COUPON,
            content="DISCOUNT20",
        )
        result = render_overlay(overlay)
        assert isinstance(result, bytes)
        assert b"DISCOUNT20" in result

    def test_overlay_type_enum(self):
        assert int(OverlayType.PRODUCT_CARD) == 1
        assert int(OverlayType.PRICE_TAG) == 2
        assert int(OverlayType.COUPON) == 3
        assert int(OverlayType.WATERMARK) == 4
        assert int(OverlayType.LOGO) == 5


# ── gRPC Tests ──


class TestGrpcRender:
    """Tests for the Render RPC."""

    @pytest.mark.asyncio
    async def test_render_basic(self, grpc_service, mock_context):
        request = render_pb2.RenderRequest(
            request_id="test_001",
            avatar_id="avatar_001",
            audio_data=b"\x00\x00" * 16000,
            video_config=render_pb2.VideoConfig(width=1920, height=1080, fps=30),
        )
        response = await grpc_service.Render(request, mock_context)
        assert response.request_id == "test_001"
        assert response.is_final
        assert len(response.video_frame) > 0

    @pytest.mark.asyncio
    async def test_render_missing_avatar(self, grpc_service, mock_context):
        request = render_pb2.RenderRequest(
            request_id="test_002",
            avatar_id="",
        )
        response = await grpc_service.Render(request, mock_context)
        assert mock_context.code.name == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_render_with_overlays(self, grpc_service, mock_context):
        overlay = render_pb2.Overlay(
            overlay_id="product_1",
            type=render_pb2.OVERLAY_TYPE_PRODUCT_CARD,
            content='{"product_id": "p001"}',
            position=render_pb2.Position(x=100, y=100, width=200, height=300, opacity=0.9),
        )
        request = render_pb2.RenderRequest(
            request_id="test_003",
            avatar_id="avatar_001",
            audio_data=b"\x00\x00" * 8000,
            overlays=[overlay],
        )
        response = await grpc_service.Render(request, mock_context)
        assert response.is_final
        assert len(response.video_frame) > 0


class TestGrpcPredictLipSync:
    """Tests for the PredictLipSync RPC."""

    @pytest.mark.asyncio
    async def test_predict_basic(self, grpc_service, mock_context):
        request = render_pb2.PredictLipSyncRequest(
            audio_data=b"\x00\x00" * 16000,
            sample_rate=16000,
            avatar_id="avatar_001",
        )
        response = await grpc_service.PredictLipSync(request, mock_context)
        assert response.frame_count > 0
        assert len(response.blendshape_weights) > 0
        expected_len = response.frame_count * 52
        assert len(response.blendshape_weights) == expected_len

    @pytest.mark.asyncio
    async def test_predict_no_audio(self, grpc_service, mock_context):
        request = render_pb2.PredictLipSyncRequest(audio_data=b"")
        response = await grpc_service.PredictLipSync(request, mock_context)
        assert mock_context.code.name == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_predict_deterministic(self, grpc_service, mock_context):
        audio = b"\x01\x02" * 8000
        req1 = render_pb2.PredictLipSyncRequest(audio_data=audio)
        req2 = render_pb2.PredictLipSyncRequest(audio_data=audio)
        resp1 = await grpc_service.PredictLipSync(req1, mock_context)
        resp2 = await grpc_service.PredictLipSync(req2, mock_context)
        assert resp1.blendshape_weights == resp2.blendshape_weights


class TestGrpcGPUStatus:
    """Tests for the GetGPUStatus RPC."""

    @pytest.mark.asyncio
    async def test_gpu_status(self, grpc_service, mock_context):
        request = render_pb2.GetGPUStatusRequest()
        status = await grpc_service.GetGPUStatus(request, mock_context)
        assert status.total_memory_mb > 0
        assert status.used_memory_mb > 0
        assert 0 <= status.gpu_utilization_pct <= 100


# ── HTTP Tests ──


class TestHttpHealth:
    """Tests for GET /api/v1/health."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"


class TestHttpRender:
    """Tests for POST /api/v1/render."""

    @pytest.mark.asyncio
    async def test_render_basic(self, client):
        response = await client.post(
            "/api/v1/render",
            json={
                "avatar_id": "avatar_001",
                "width": 1920,
                "height": 1080,
                "fps": 30,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "frame_base64" in data
        assert data["is_final"]

    @pytest.mark.asyncio
    async def test_render_with_audio(self, client):
        import base64

        audio_b64 = base64.b64encode(b"\x00\x00" * 16000).decode()
        response = await client.post(
            "/api/v1/render",
            json={
                "avatar_id": "avatar_001",
                "audio_base64": audio_b64,
            },
        )
        assert response.status_code == 200


class TestHttpPredictLipSync:
    """Tests for POST /api/v1/predict-lipsync."""

    @pytest.mark.asyncio
    async def test_predict_lipsync(self, client):
        import base64

        audio_b64 = base64.b64encode(b"\x00\x00" * 16000).decode()
        response = await client.post(
            "/api/v1/predict-lipsync",
            json={
                "audio_base64": audio_b64,
                "sample_rate": 16000,
                "avatar_id": "avatar_001",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["frame_count"] > 0
        assert len(data["blendshape_weights"]) > 0


class TestHttpGPUStatus:
    """Tests for GET /api/v1/gpu-status."""

    @pytest.mark.asyncio
    async def test_gpu_status(self, client):
        response = await client.get("/api/v1/gpu-status")
        assert response.status_code == 200
        data = response.json()
        assert data["total_memory_mb"] > 0
        assert "device_name" in data
