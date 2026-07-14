"""
Mock RTMP/SRT push management.

In production this would use FFmpeg or a custom RTMP/SRT library to
push encoded video frames to a CDN / streaming platform. Here we
simulate stream session lifecycle with in-memory state.

StreamSession lifecycle:
  CREATED -> CONNECTING -> STREAMING -> DISCONNECTED / ERROR
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from libs.common.logging import get_logger

logger = get_logger(__name__)


# ── Stream Status ──


class StreamStatus(IntEnum):
    UNSPECIFIED = 0
    CONNECTING = 1
    STREAMING = 2
    DISCONNECTED = 3
    ERROR = 4


# ── Data Models ──


@dataclass
class StreamSessionState:
    """In-memory state for an active stream push session."""

    session_id: str
    live_room_id: str
    status: StreamStatus = StreamStatus.UNSPECIFIED
    rtmp_url: str = ""
    stream_key: str = ""
    started_at: int = 0
    bytes_sent: int = 0
    fps: int = 30
    bitrate_kbps: int = 4500
    dropped_frames: int = 0
    health_score: float = 1.0
    platforms: list[dict[str, Any]] = field(default_factory=list)


# ── Push Manager ──


class PushManager:
    """Manages stream push sessions (mock)."""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config
        self._sessions: dict[str, StreamSessionState] = {}

    def create_session(
        self,
        live_room_id: str,
        rtmp_base_url: str = "rtmp://push.livestream-tts.com/live",
    ) -> StreamSessionState:
        """Create a new stream push session.

        Args:
            live_room_id: Identifier for the live room.
            rtmp_base_url: Base RTMP URL for the stream.

        Returns:
            The newly created StreamSessionState.
        """
        session_id = f"stream-{uuid.uuid4().hex[:12]}"
        stream_key = f"livestream_{live_room_id}_{uuid.uuid4().hex[:8]}"
        rtmp_url = f"{rtmp_base_url}/{stream_key}"

        session = StreamSessionState(
            session_id=session_id,
            live_room_id=live_room_id,
            status=StreamStatus.CONNECTING,
            rtmp_url=rtmp_url,
            stream_key=stream_key,
            started_at=int(time.time() * 1000),
            platforms=[
                {"platform": "default", "rtmp_url": rtmp_url},
            ],
        )

        self._sessions[session_id] = session
        logger.info(
            "push.session_created",
            session_id=session_id,
            live_room_id=live_room_id,
            rtmp_url=rtmp_url,
        )

        # Simulate connection handshake: move to STREAMING after creation
        self._sessions[session_id].status = StreamStatus.STREAMING
        return session

    def stop_session(self, session_id: str) -> bool:
        """Stop a stream push session.

        Args:
            session_id: The session to stop.

        Returns:
            True if the session was found and stopped.
        """
        session = self._sessions.get(session_id)
        if not session:
            logger.warning("push.session_not_found", session_id=session_id)
            return False

        session.status = StreamStatus.DISCONNECTED
        logger.info(
            "push.session_stopped",
            session_id=session_id,
            uptime_ms=int(time.time() * 1000) - session.started_at,
        )
        return True

    def get_session(self, session_id: str) -> StreamSessionState | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def get_status(self, session_id: str) -> dict[str, Any]:
        """Get push status for a session.

        Returns a dict with status info, or an empty dict if not found.
        """
        session = self._sessions.get(session_id)
        if not session:
            return {}

        uptime_seconds = 0
        if session.started_at:
            uptime_seconds = int((time.time() * 1000 - session.started_at) / 1000)

        # Simulate slight health degradation over time
        health = max(0.5, 1.0 - uptime_seconds * 0.001)

        return {
            "session_id": session.session_id,
            "status": session.status,
            "fps": session.fps,
            "bitrate_kbps": session.bitrate_kbps,
            "uptime_seconds": uptime_seconds,
            "dropped_frames": int(uptime_seconds * 0.3),
            "health_score": round(health, 2),
        }
