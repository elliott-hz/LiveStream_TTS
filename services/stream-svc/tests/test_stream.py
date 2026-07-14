"""
Unit tests for the Stream Service (gRPC + HTTP + streamer modules).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

# Monorepo path setup
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
STREAM_SVC_ROOT = REPO_ROOT / "services" / "stream-svc"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(STREAM_SVC_ROOT))

from src.api.grpc_impl import StreamGrpcService
from src.http.routes import create_http_app
from src.streamer.push import PushManager, StreamStatus, StreamSessionState
from src.streamer.recorder import RecorderManager, RecordingStatus, RecordingState
from src.streamer.transcoder import TranscodeManager, TranscodeStatus, TranscodeJobState
from libs.proto.stream.v1 import stream_pb2
from libs.proto.common.v1 import common_pb2


# ── Fixtures ──


@pytest.fixture
def grpc_service():
    return StreamGrpcService()


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


# ── PushManager Tests ──


class TestPushManager:
    """Tests for the PushManager."""

    def test_create_session(self):
        mgr = PushManager()
        session = mgr.create_session("room_001")
        assert session.session_id.startswith("stream-")
        assert session.live_room_id == "room_001"
        assert session.status == StreamStatus.STREAMING
        assert session.rtmp_url.startswith("rtmp://")
        assert len(session.stream_key) > 0

    def test_create_session_generates_unique_ids(self):
        mgr = PushManager()
        s1 = mgr.create_session("room_001")
        s2 = mgr.create_session("room_001")
        assert s1.session_id != s2.session_id
        assert s1.stream_key != s2.stream_key

    def test_stop_existing_session(self):
        mgr = PushManager()
        session = mgr.create_session("room_001")
        result = mgr.stop_session(session.session_id)
        assert result is True
        updated = mgr.get_session(session.session_id)
        assert updated.status == StreamStatus.DISCONNECTED

    def test_stop_nonexistent_session(self):
        mgr = PushManager()
        result = mgr.stop_session("nonexistent")
        assert result is False

    def test_get_status(self):
        mgr = PushManager()
        session = mgr.create_session("room_001")
        status = mgr.get_status(session.session_id)
        assert status["session_id"] == session.session_id
        assert status["status"] == StreamStatus.STREAMING
        assert status["fps"] == 30
        assert status["bitrate_kbps"] == 4500
        assert status["uptime_seconds"] >= 0
        assert status["health_score"] <= 1.0

    def test_get_status_nonexistent(self):
        mgr = PushManager()
        status = mgr.get_status("nonexistent")
        assert status == {}


# ── RecorderManager Tests ──


class TestRecorderManager:
    """Tests for the RecorderManager."""

    def test_start_recording(self):
        mgr = RecorderManager()
        rec = mgr.start_recording("room_001")
        assert rec.recording_id.startswith("rec-")
        assert rec.live_room_id == "room_001"
        assert rec.status == RecordingStatus.RECORDING
        assert rec.hls_url.endswith("index.m3u8")

    def test_stop_recording(self):
        mgr = RecorderManager()
        rec = mgr.start_recording("room_001")
        stopped = mgr.stop_recording(rec.recording_id)
        assert stopped is not None
        assert stopped.status == RecordingStatus.COMPLETED
        assert stopped.duration_seconds > 0
        assert stopped.file_size_bytes > 0

    def test_stop_nonexistent_recording(self):
        mgr = RecorderManager()
        result = mgr.stop_recording("nonexistent")
        assert result is None

    def test_get_recording(self):
        mgr = RecorderManager()
        rec = mgr.start_recording("room_001")
        fetched = mgr.get_recording(rec.recording_id)
        assert fetched is not None
        assert fetched.recording_id == rec.recording_id

    def test_get_nonexistent_recording(self):
        mgr = RecorderManager()
        assert mgr.get_recording("nonexistent") is None


# ── TranscodeManager Tests ──


class TestTranscodeManager:
    """Tests for the TranscodeManager."""

    def test_create_job(self):
        mgr = TranscodeManager()
        job = mgr.create_job("rec_001")
        assert job.job_id.startswith("tc-")
        assert job.status == TranscodeStatus.COMPLETED
        assert job.progress_percent == 100

    def test_create_job_with_custom_target(self):
        mgr = TranscodeManager()
        job = mgr.create_job(
            "rec_001",
            target_width=1280,
            target_height=720,
            target_fps=60,
            target_bitrate_kbps=3000,
            target_format="mkv",
        )
        assert job.target_width == 1280
        assert job.target_height == 720
        assert job.target_fps == 60
        assert job.target_bitrate_kbps == 3000
        assert job.target_format == "mkv"

    def test_get_job(self):
        mgr = TranscodeManager()
        job = mgr.create_job("rec_001")
        fetched = mgr.get_job(job.job_id)
        assert fetched is not None
        assert fetched.job_id == job.job_id

    def test_get_nonexistent_job(self):
        mgr = TranscodeManager()
        assert mgr.get_job("nonexistent") is None


# ── gRPC Tests ──


class TestGrpcStartPush:
    """Tests for the StartPush RPC."""

    @pytest.mark.asyncio
    async def test_start_push_basic(self, grpc_service, mock_context):
        request = stream_pb2.StartPushRequest(live_room_id="room_001")
        session = await grpc_service.StartPush(request, mock_context)
        assert session.session_id.startswith("stream-")
        assert session.live_room_id == "room_001"
        assert session.status == stream_pb2.STREAM_STATUS_STREAMING
        assert len(session.rtmp_url) > 0
        assert len(session.platforms) > 0

    @pytest.mark.asyncio
    async def test_start_push_missing_room_id(self, grpc_service, mock_context):
        request = stream_pb2.StartPushRequest(live_room_id="")
        session = await grpc_service.StartPush(request, mock_context)
        assert mock_context.code.name == "INVALID_ARGUMENT"


class TestGrpcStopPush:
    """Tests for the StopPush RPC."""

    @pytest.mark.asyncio
    async def test_stop_existing_session(self, grpc_service, mock_context):
        # Create
        create_req = stream_pb2.StartPushRequest(live_room_id="room_001")
        session = await grpc_service.StartPush(create_req, mock_context)

        # Stop
        stop_req = stream_pb2.StopPushRequest(session_id=session.session_id)
        error = await grpc_service.StopPush(stop_req, mock_context)
        assert error.code == 0
        assert error.message == "stopped"

    @pytest.mark.asyncio
    async def test_stop_nonexistent(self, grpc_service, mock_context):
        request = stream_pb2.StopPushRequest(session_id="nonexistent")
        error = await grpc_service.StopPush(request, mock_context)
        assert mock_context.code.name == "NOT_FOUND"


class TestGrpcGetPushStatus:
    """Tests for the GetPushStatus RPC."""

    @pytest.mark.asyncio
    async def test_get_status(self, grpc_service, mock_context):
        create_req = stream_pb2.StartPushRequest(live_room_id="room_001")
        session = await grpc_service.StartPush(create_req, mock_context)

        status_req = stream_pb2.GetPushStatusRequest(session_id=session.session_id)
        status = await grpc_service.GetPushStatus(status_req, mock_context)
        assert status.fps > 0
        assert status.bitrate_kbps > 0
        assert status.uptime_seconds >= 0

    @pytest.mark.asyncio
    async def test_get_status_nonexistent(self, grpc_service, mock_context):
        request = stream_pb2.GetPushStatusRequest(session_id="nonexistent")
        status = await grpc_service.GetPushStatus(request, mock_context)
        assert mock_context.code.name == "NOT_FOUND"


class TestGrpcRecording:
    """Tests for StartRecording / StopRecording RPCs."""

    @pytest.mark.asyncio
    async def test_start_recording(self, grpc_service, mock_context):
        request = stream_pb2.StartRecordingRequest(
            live_room_id="room_001",
            format="hls",
        )
        recording = await grpc_service.StartRecording(request, mock_context)
        assert recording.recording_id.startswith("rec-")
        assert recording.status == stream_pb2.RECORDING_STATUS_RECORDING
        assert recording.hls_url.endswith("index.m3u8")

    @pytest.mark.asyncio
    async def test_start_recording_missing_room(self, grpc_service, mock_context):
        request = stream_pb2.StartRecordingRequest(live_room_id="")
        recording = await grpc_service.StartRecording(request, mock_context)
        assert mock_context.code.name == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_stop_recording(self, grpc_service, mock_context):
        start_req = stream_pb2.StartRecordingRequest(live_room_id="room_001")
        recording = await grpc_service.StartRecording(start_req, mock_context)

        stop_req = stream_pb2.StopRecordingRequest(
            recording_id=recording.recording_id,
        )
        stopped = await grpc_service.StopRecording(stop_req, mock_context)
        assert stopped.status == stream_pb2.RECORDING_STATUS_COMPLETED
        assert stopped.duration_seconds > 0
        assert stopped.file_size_bytes > 0

    @pytest.mark.asyncio
    async def test_stop_nonexistent(self, grpc_service, mock_context):
        request = stream_pb2.StopRecordingRequest(recording_id="nonexistent")
        recording = await grpc_service.StopRecording(request, mock_context)
        assert mock_context.code.name == "NOT_FOUND"


class TestGrpcTranscode:
    """Tests for Transcode / GetTranscodeJob RPCs."""

    @pytest.mark.asyncio
    async def test_transcode(self, grpc_service, mock_context):
        request = stream_pb2.TranscodeRequest(
            recording_id="rec_001",
            target=stream_pb2.TranscodeRequest.VideoConfig(
                width=1920,
                height=1080,
                fps=30,
                bitrate_kbps=5000,
                format="mp4",
            ),
        )
        job = await grpc_service.Transcode(request, mock_context)
        assert job.job_id.startswith("tc-")
        assert job.status == stream_pb2.TRANSCODE_STATUS_COMPLETED
        assert job.progress_percent == 100

    @pytest.mark.asyncio
    async def test_transcode_missing_recording(self, grpc_service, mock_context):
        request = stream_pb2.TranscodeRequest(recording_id="")
        job = await grpc_service.Transcode(request, mock_context)
        assert mock_context.code.name == "INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_get_transcode_job(self, grpc_service, mock_context):
        create_req = stream_pb2.TranscodeRequest(
            recording_id="rec_001",
        )
        created = await grpc_service.Transcode(create_req, mock_context)

        get_req = stream_pb2.GetTranscodeJobRequest(job_id=created.job_id)
        fetched = await grpc_service.GetTranscodeJob(get_req, mock_context)
        assert fetched.job_id == created.job_id
        assert fetched.progress_percent == 100

    @pytest.mark.asyncio
    async def test_get_nonexistent_job(self, grpc_service, mock_context):
        request = stream_pb2.GetTranscodeJobRequest(job_id="nonexistent")
        job = await grpc_service.GetTranscodeJob(request, mock_context)
        assert mock_context.code.name == "NOT_FOUND"


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


class TestHttpStreamPush:
    """Tests for HTTP stream push endpoints."""

    @pytest.mark.asyncio
    async def test_start_push(self, client):
        response = await client.post(
            "/api/v1/stream/start",
            json={"live_room_id": "room_001"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"].startswith("stream-")
        assert data["status"] == "STREAMING"

    @pytest.mark.asyncio
    async def test_start_push_missing_room(self, client):
        response = await client.post(
            "/api/v1/stream/start",
            json={"live_room_id": ""},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_stop_push(self, client):
        # Start
        start_resp = await client.post(
            "/api/v1/stream/start",
            json={"live_room_id": "room_stop"},
        )
        session_id = start_resp.json()["session_id"]

        # Stop
        stop_resp = await client.post(
            "/api/v1/stream/stop",
            json={"session_id": session_id},
        )
        assert stop_resp.status_code == 200
        assert stop_resp.json()["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_stop_nonexistent(self, client):
        response = await client.post(
            "/api/v1/stream/stop",
            json={"session_id": "nonexistent"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_push_status(self, client):
        # Start
        start_resp = await client.post(
            "/api/v1/stream/start",
            json={"live_room_id": "room_status"},
        )
        session_id = start_resp.json()["session_id"]

        # Get status
        status_resp = await client.get(f"/api/v1/stream/{session_id}")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["fps"] > 0
        assert data["bitrate_kbps"] > 0

    @pytest.mark.asyncio
    async def test_get_nonexistent_status(self, client):
        response = await client.get("/api/v1/stream/nonexistent")
        assert response.status_code == 404
