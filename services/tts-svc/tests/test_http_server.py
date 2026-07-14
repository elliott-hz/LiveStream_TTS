"""
Unit tests for the TTS HTTP server (FastAPI REST + WebSocket).

Tests health, voice CRUD, synthesis, and WebSocket endpoints.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

# Monorepo path setup
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
TTS_SVC_ROOT = REPO_ROOT / "services" / "tts-svc"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TTS_SVC_ROOT))

from src.http_server import create_http_app
from src.grpc_service import TTSGrpcService, VoiceStore


# ── Fixtures ──

@pytest.fixture
def voice_store():
    return VoiceStore()


@pytest.fixture
def grpc_service(voice_store):
    return TTSGrpcService(voice_store=voice_store)


@pytest.fixture
def app(grpc_service, voice_store):
    return create_http_app(grpc_service, voice_store)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Health Check Tests ──

class TestHealth:
    """Tests for GET /api/v1/health."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.2.0"
        assert isinstance(data["uptime_seconds"], int)


# ── Voice CRUD Tests ──

class TestVoiceCRUD:
    """Tests for /api/v1/voices endpoints."""

    @pytest.mark.asyncio
    async def test_list_voices(self, client):
        response = await client.get("/api/v1/voices")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(v["voice_id"] == "default" for v in data["voices"])

    @pytest.mark.asyncio
    async def test_get_default_voice(self, client):
        response = await client.get("/api/v1/voices/default")
        assert response.status_code == 200
        data = response.json()
        assert data["voice_id"] == "default"

    @pytest.mark.asyncio
    async def test_get_nonexistent_voice(self, client):
        response = await client.get("/api/v1/voices/nonexistent")
        assert response.status_code == 404
        detail = response.json()
        if "detail" in detail:
            detail = detail["detail"]
        assert detail["error_code"] == 3007

    @pytest.mark.asyncio
    async def test_create_voice(self, client):
        response = await client.post(
            "/api/v1/voices",
            json={
                "name": "HTTP Test Voice",
                "gender": 1,
                "language": "en-US",
                "style": 2,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "HTTP Test Voice"
        assert data["gender"] == "GENDER_MALE"
        assert data["voice_id"].startswith("voice-")

    @pytest.mark.asyncio
    async def test_delete_voice(self, client):
        # Create a voice first
        create_resp = await client.post(
            "/api/v1/voices",
            json={"name": "To Delete"},
        )
        voice_id = create_resp.json()["voice_id"]

        # Delete it
        delete_resp = await client.delete(f"/api/v1/voices/{voice_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["status"] == "deleted"

        # Verify it's gone
        get_resp = await client.get(f"/api/v1/voices/{voice_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_default_voice_fails(self, client):
        response = await client.delete("/api/v1/voices/default")
        assert response.status_code == 404


# ── Synthesis Tests ──

class TestSynthesize:
    """Tests for POST /api/v1/synthesize."""

    @pytest.mark.asyncio
    async def test_synthesize_text(self, client):
        response = await client.post(
            "/api/v1/synthesize",
            json={
                "text": "你好世界",
                "voice_id": "default",
                "speed": 1.0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "audio_base64" in data
        assert data["duration_ms"] > 0
        assert data["total_chunks"] > 0
        assert data["sample_rate"] == 16000

    @pytest.mark.asyncio
    async def test_synthesize_empty_text(self, client):
        response = await client.post(
            "/api/v1/synthesize",
            json={"text": "", "voice_id": "default"},
        )
        assert response.status_code == 500  # Error from pipeline

    @pytest.mark.asyncio
    async def test_synthesize_with_emotion(self, client):
        response = await client.post(
            "/api/v1/synthesize",
            json={
                "text": "今天直播间的商品非常棒",
                "voice_id": "default",
                "emotion": "excited",
                "speed": 1.2,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["audio_base64"]) > 0


# ── WebSocket Tests ──

class TestWebSocket:
    """Tests for /ws/v1/tts."""

    @pytest.mark.asyncio
    async def test_websocket_synthesis(self, client, app):
        from fastapi.testclient import TestClient

        ws_client = TestClient(app)
        with ws_client.websocket_connect("/ws/v1/tts") as ws:
            # Send a synthesis request
            ws.send_json({
                "type": "synthesis_request",
                "request_id": "ws_test_001",
                "text": "测试WebSocket",
                "voice_id": "default",
                "emotion": "neutral",
                "speed": 1.0,
            })

            # Receive responses
            audio_chunks = 0
            completed = False
            for _ in range(100):  # limit iterations
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "audio_chunk":
                    audio_chunks += 1
                elif msg["type"] == "synthesis_complete":
                    completed = True
                    break
                elif msg["type"] == "error":
                    break

            assert audio_chunks > 0, "Should receive audio chunks"
            assert completed, "Should complete synthesis"

    @pytest.mark.asyncio
    async def test_websocket_ping_pong(self, client, app):
        from fastapi.testclient import TestClient

        ws_client = TestClient(app)
        with ws_client.websocket_connect("/ws/v1/tts") as ws:
            ws.send_json({"type": "ping"})
            response = ws.receive_text()
            msg = json.loads(response)
            assert msg["type"] == "pong"
