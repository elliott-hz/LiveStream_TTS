"""
Stream gRPC Service Implementation — StreamServiceServicer.

Implements all RPCs from libs/proto/stream/v1/stream.proto:
  - StartPush          — Create StreamSession, return RTMP URL, simulate streaming status
  - StopPush           — Mark session disconnected
  - GetPushStatus      — Return mock FPS/bitrate/uptime
  - StartRecording     — Mock HLS recording start
  - StopRecording      — Mock HLS recording stop
  - Transcode          — Mock transcode job creation
  - GetTranscodeJob    — Get transcode job status
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import grpc

# Monorepo path setup
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
STREAM_SVC_ROOT = REPO_ROOT / "services" / "stream-svc"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(STREAM_SVC_ROOT))

from libs.common.errors import (
    ErrorCode,
    Domain,
    AppError,
    not_found,
    invalid_arg,
    internal,
)
from libs.common.logging import get_logger

from libs.proto.stream.v1 import stream_pb2, stream_pb2_grpc
from libs.proto.common.v1 import common_pb2

from src.streamer.push import PushManager, StreamStatus
from src.streamer.recorder import RecorderManager, RecordingStatus
from src.streamer.transcoder import TranscodeManager, TranscodeStatus
from src.config import StreamConfig

logger = get_logger(__name__)


# ── gRPC Servicer ──


class StreamGrpcService(stream_pb2_grpc.StreamServiceServicer):
    """gRPC servicer for the StreamService."""

    def __init__(self, config: StreamConfig | None = None) -> None:
        self.config = config or StreamConfig()
        self.push_manager = PushManager(config=self.config)
        self.recorder = RecorderManager(
            recording_dir=self.config.recording_dir,
        )
        self.transcoder = TranscodeManager(
            queue_size=self.config.transcode_queue_size,
        )
        self._start_time = time.time()

    # ── Push Stream ──

    async def StartPush(
        self,
        request: stream_pb2.StartPushRequest,
        context: grpc.aio.ServicerContext,
    ) -> stream_pb2.StreamSession:
        """Create a stream session and return RTMP URL."""
        logger.info(
            "grpc.start_push",
            live_room_id=request.live_room_id,
        )

        if not request.live_room_id:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("live_room_id is required")
            return stream_pb2.StreamSession()

        session = self.push_manager.create_session(
            live_room_id=request.live_room_id,
            rtmp_base_url=self.config.rtmp_base_url,
        )

        return stream_pb2.StreamSession(
            session_id=session.session_id,
            live_room_id=session.live_room_id,
            status=stream_pb2.STREAM_STATUS_STREAMING,
            rtmp_url=session.rtmp_url,
            stream_key=session.stream_key,
            platforms=[
                stream_pb2.PlatformStream(
                    platform=p["platform"],
                    rtmp_url=p["rtmp_url"],
                    status=stream_pb2.STREAM_STATUS_STREAMING,
                )
                for p in session.platforms
            ],
            started_at=session.started_at,
            bytes_sent=session.bytes_sent,
        )

    async def StopPush(
        self,
        request: stream_pb2.StopPushRequest,
        context: grpc.aio.ServicerContext,
    ) -> common_pb2.Error:
        """Stop a stream push session."""
        logger.info("grpc.stop_push", session_id=request.session_id)

        ok = self.push_manager.stop_session(request.session_id)
        if not ok:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"session not found: {request.session_id}")
            return common_pb2.Error(
                code=ErrorCode.NOT_FOUND,
                message=f"session not found: {request.session_id}",
            )

        return common_pb2.Error(code=0, message="stopped")

    async def GetPushStatus(
        self,
        request: stream_pb2.GetPushStatusRequest,
        context: grpc.aio.ServicerContext,
    ) -> stream_pb2.PushStatus:
        """Return mock FPS/bitrate/uptime for a push session."""
        logger.debug("grpc.get_push_status", session_id=request.session_id)

        status_data = self.push_manager.get_status(request.session_id)
        if not status_data:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"session not found: {request.session_id}")
            return stream_pb2.PushStatus()

        return stream_pb2.PushStatus(
            session_id=status_data["session_id"],
            status=stream_pb2.StreamStatus.Value(
                f"STREAM_STATUS_{status_data['status'].name}"
            ),
            fps=status_data["fps"],
            bitrate_kbps=status_data["bitrate_kbps"],
            uptime_seconds=status_data["uptime_seconds"],
            dropped_frames=status_data["dropped_frames"],
            health_score=status_data["health_score"],
        )

    # ── Recording ──

    async def StartRecording(
        self,
        request: stream_pb2.StartRecordingRequest,
        context: grpc.aio.ServicerContext,
    ) -> stream_pb2.Recording:
        """Mock HLS recording start."""
        logger.info(
            "grpc.start_recording",
            live_room_id=request.live_room_id,
            format=request.format,
        )

        if not request.live_room_id:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("live_room_id is required")
            return stream_pb2.Recording()

        recording = self.recorder.start_recording(
            live_room_id=request.live_room_id,
            fmt=request.format or "hls",
        )

        return stream_pb2.Recording(
            recording_id=recording.recording_id,
            live_room_id=recording.live_room_id,
            status=stream_pb2.RECORDING_STATUS_RECORDING,
            hls_url=recording.hls_url,
            mp4_url=recording.mp4_url,
            started_at=recording.started_at,
        )

    async def StopRecording(
        self,
        request: stream_pb2.StopRecordingRequest,
        context: grpc.aio.ServicerContext,
    ) -> stream_pb2.Recording:
        """Mock HLS recording stop."""
        logger.info("grpc.stop_recording", recording_id=request.recording_id)

        recording = self.recorder.stop_recording(request.recording_id)
        if not recording:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"recording not found: {request.recording_id}")
            return stream_pb2.Recording()

        return stream_pb2.Recording(
            recording_id=recording.recording_id,
            live_room_id=recording.live_room_id,
            status=stream_pb2.RECORDING_STATUS_COMPLETED,
            hls_url=recording.hls_url,
            mp4_url=recording.mp4_url,
            file_size_bytes=recording.file_size_bytes,
            duration_seconds=recording.duration_seconds,
            started_at=recording.started_at,
        )

    # ── Transcoding ──

    async def Transcode(
        self,
        request: stream_pb2.TranscodeRequest,
        context: grpc.aio.ServicerContext,
    ) -> stream_pb2.TranscodeJob:
        """Mock transcode job creation."""
        logger.info(
            "grpc.transcode",
            recording_id=request.recording_id,
            target=f"{request.target.width}x{request.target.height}",
        )

        if not request.recording_id:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("recording_id is required")
            return stream_pb2.TranscodeJob()

        target = request.target
        job = self.transcoder.create_job(
            recording_id=request.recording_id,
            target_width=target.width or 1920,
            target_height=target.height or 1080,
            target_fps=target.fps or 30,
            target_bitrate_kbps=target.bitrate_kbps or 5000,
            target_format=target.format or "mp4",
        )

        return stream_pb2.TranscodeJob(
            job_id=job.job_id,
            status=stream_pb2.TRANSCODE_STATUS_COMPLETED,
            input_url=job.input_url,
            output_url=job.output_url,
            progress_percent=job.progress_percent,
        )

    async def GetTranscodeJob(
        self,
        request: stream_pb2.GetTranscodeJobRequest,
        context: grpc.aio.ServicerContext,
    ) -> stream_pb2.TranscodeJob:
        """Get transcode job status."""
        logger.debug("grpc.get_transcode_job", job_id=request.job_id)

        job = self.transcoder.get_job(request.job_id)
        if not job:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"transcode job not found: {request.job_id}")
            return stream_pb2.TranscodeJob()

        return stream_pb2.TranscodeJob(
            job_id=job.job_id,
            status=stream_pb2.TRANSCODE_STATUS_COMPLETED,
            input_url=job.input_url,
            output_url=job.output_url,
            progress_percent=job.progress_percent,
        )
