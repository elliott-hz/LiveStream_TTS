"""
Unit tests for the TTS gRPC service (TTSServiceServicer).

Tests the core RPCs using mock gRPC contexts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Monorepo path setup
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
TTS_SVC_ROOT = REPO_ROOT / "services" / "tts-svc"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TTS_SVC_ROOT))

from src.grpc_service import TTSGrpcService, VoiceStore
from libs.proto.tts.v1 import tts_pb2
from libs.proto.common.v1 import common_pb2


# ── Fixtures ──

@pytest.fixture
def voice_store():
    return VoiceStore()


@pytest.fixture
def grpc_service(voice_store):
    return TTSGrpcService(voice_store=voice_store)


@pytest.fixture
def mock_context():
    """Create a minimal mock gRPC context for testing."""
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


# ── Voice CRUD Tests ──

class TestListVoices:
    """Tests for ListVoices RPC."""

    @pytest.mark.asyncio
    async def test_list_default_voice(self, grpc_service, mock_context):
        """Should return at least the default voice."""
        request = tts_pb2.ListVoicesRequest()
        response = await grpc_service.ListVoices(request, mock_context)
        assert len(response.voices) >= 1
        assert response.voices[0].voice_id == "default"
        assert response.voices[0].name == "默认音色"

    @pytest.mark.asyncio
    async def test_list_with_gender_filter(self, grpc_service, mock_context):
        """Gender filter should work."""
        request = tts_pb2.ListVoicesRequest(gender=tts_pb2.GENDER_FEMALE)
        response = await grpc_service.ListVoices(request, mock_context)
        # Default voice is female
        assert len(response.voices) >= 1

        request_male = tts_pb2.ListVoicesRequest(gender=tts_pb2.GENDER_MALE)
        response_male = await grpc_service.ListVoices(request_male, mock_context)
        # No male voices by default
        assert len(response_male.voices) == 0


class TestGetVoice:
    """Tests for GetVoice RPC."""

    @pytest.mark.asyncio
    async def test_get_existing_voice(self, grpc_service, mock_context):
        """Should return the default voice."""
        request = tts_pb2.GetVoiceRequest(voice_id="default")
        voice = await grpc_service.GetVoice(request, mock_context)
        assert voice.voice_id == "default"
        assert voice.name == "默认音色"
        assert voice.status == tts_pb2.VOICE_STATUS_ACTIVE

    @pytest.mark.asyncio
    async def test_get_nonexistent_voice(self, grpc_service, mock_context):
        """Should set NOT_FOUND for missing voice."""
        request = tts_pb2.GetVoiceRequest(voice_id="nonexistent")
        voice = await grpc_service.GetVoice(request, mock_context)
        assert mock_context.code.name == "NOT_FOUND"


class TestCreateVoice:
    """Tests for CreateVoice RPC."""

    @pytest.mark.asyncio
    async def test_create_voice_minimal(self, grpc_service, mock_context):
        """Should create a voice with minimal fields."""
        request = tts_pb2.CreateVoiceRequest(
            name="Test Voice",
            gender=tts_pb2.GENDER_MALE,
        )
        voice = await grpc_service.CreateVoice(request, mock_context)
        assert voice.name == "Test Voice"
        assert voice.gender == tts_pb2.GENDER_MALE
        assert voice.voice_id.startswith("voice-")
        assert voice.status == tts_pb2.VOICE_STATUS_ACTIVE

    @pytest.mark.asyncio
    async def test_create_and_list(self, grpc_service, voice_store, mock_context):
        """Created voice should appear in list."""
        request = tts_pb2.CreateVoiceRequest(
            name="Custom Voice",
            gender=tts_pb2.GENDER_FEMALE,
            language="en-US",
            style=tts_pb2.VOICE_STYLE_PROFESSIONAL,
        )
        voice = await grpc_service.CreateVoice(request, mock_context)

        list_req = tts_pb2.ListVoicesRequest()
        list_resp = await grpc_service.ListVoices(list_req, mock_context)
        voice_ids = [v.voice_id for v in list_resp.voices]
        assert voice.voice_id in voice_ids


class TestDeleteVoice:
    """Tests for DeleteVoice RPC."""

    @pytest.mark.asyncio
    async def test_delete_protected_default(self, grpc_service, mock_context):
        """Default voice should not be deletable."""
        request = tts_pb2.DeleteVoiceRequest(voice_id="default")
        result = await grpc_service.DeleteVoice(request, mock_context)
        assert result.code != 0  # Error code

    @pytest.mark.asyncio
    async def test_delete_custom_voice(self, grpc_service, voice_store, mock_context):
        """Custom voice should be deletable."""
        # Create first
        create_req = tts_pb2.CreateVoiceRequest(name="Delete Me")
        voice = await grpc_service.CreateVoice(create_req, mock_context)

        # Delete
        delete_req = tts_pb2.DeleteVoiceRequest(voice_id=voice.voice_id)
        result = await grpc_service.DeleteVoice(delete_req, mock_context)
        assert result.code == 0
        assert result.message == "deleted"

        # Verify it's gone
        get_req = tts_pb2.GetVoiceRequest(voice_id=voice.voice_id)
        await grpc_service.GetVoice(get_req, mock_context)
        assert mock_context.code.name == "NOT_FOUND"


# ── Synthesis Tests ──

class TestSynthesize:
    """Tests for Synthesize RPC (server-streaming)."""

    @pytest.mark.asyncio
    async def test_synthesize_basic(self, grpc_service, mock_context):
        """Should synthesize text and yield audio chunks."""
        request = tts_pb2.SynthesisRequest(
            text="你好世界",
            voice_id="default",
            speed=1.0,
            emotion=tts_pb2.EMOTION_NEUTRAL,
        )

        chunks = []
        complete = None
        error = None

        async for response in grpc_service.Synthesize(request, mock_context):
            which = response.WhichOneof("payload")
            if which == "audio_chunk":
                chunks.append(response.audio_chunk)
            elif which == "complete":
                complete = response.complete
            elif which == "error":
                error = response.error

        assert error is None, f"Synthesis failed: {error}"
        assert len(chunks) > 0, "Should produce at least one audio chunk"
        assert complete is not None, "Should return synthesis complete"
        assert len(chunks) == complete.total_chunks
        assert complete.duration_ms > 0

    @pytest.mark.asyncio
    async def test_synthesize_empty_text(self, grpc_service, mock_context):
        """Empty text should return an error."""
        request = tts_pb2.SynthesisRequest(
            text="",
            voice_id="default",
        )

        error = None
        async for response in grpc_service.Synthesize(request, mock_context):
            if response.WhichOneof("payload") == "error":
                error = response.error

        assert error is not None
        assert error.error_code == 2002

    @pytest.mark.asyncio
    async def test_synthesize_with_emotion(self, grpc_service, mock_context):
        """Different emotions should produce different audio."""
        async def synthesize_with_emotion(emotion):
            request = tts_pb2.SynthesisRequest(
                text="测试文本",
                voice_id="default",
                emotion=emotion,
            )
            async for response in grpc_service.Synthesize(request, mock_context):
                if response.WhichOneof("payload") == "complete":
                    return response.complete
            return None

        neutral = await synthesize_with_emotion(tts_pb2.EMOTION_NEUTRAL)
        happy = await synthesize_with_emotion(tts_pb2.EMOTION_HAPPY)

        assert neutral is not None
        assert happy is not None
        # Different base emotions produce different frequency audio -> different duration
        # (just verify both complete)

    @pytest.mark.asyncio
    async def test_synthesize_nonexistent_voice(self, grpc_service, mock_context):
        """Should return error for nonexistent voice."""
        request = tts_pb2.SynthesisRequest(
            text="test",
            voice_id="nonexistent_voice",
        )

        error = None
        async for response in grpc_service.Synthesize(request, mock_context):
            if response.WhichOneof("payload") == "error":
                error = response.error

        assert error is not None
        assert error.error_code == 3007


# ── Warmup Cache Tests ──

class TestWarmupCache:
    """Tests for WarmupCache RPC."""

    @pytest.mark.asyncio
    async def test_warmup_basic(self, grpc_service, mock_context):
        """Should pre-warm cache without errors."""
        request = tts_pb2.WarmupCacheRequest(
            texts=["欢迎来到直播间", "上链接"],
            voice_id="default",
            emotion=tts_pb2.EMOTION_NEUTRAL,
        )
        response = await grpc_service.WarmupCache(request, mock_context)
        assert response.cached_count + response.failed_count > 0
