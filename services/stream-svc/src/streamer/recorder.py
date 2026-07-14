"""
Mock HLS recording management.

In production this would use FFmpeg to segment a live stream into HLS
(.m3u8 + .ts segments) and optionally produce an MP4 file. Here we
simulate recording job lifecycle in memory.

Recording lifecycle:
  RECORDING -> COMPLETED / FAILED
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from libs.common.logging import get_logger

logger = get_logger(__name__)


# ── Recording Status ──


class RecordingStatus(IntEnum):
    UNSPECIFIED = 0
    RECORDING = 1
    COMPLETED = 2
    FAILED = 3


# ── Data Models ──


@dataclass
class RecordingState:
    """In-memory state for a recording job."""

    recording_id: str
    live_room_id: str
    status: RecordingStatus = RecordingStatus.UNSPECIFIED
    hls_url: str = ""
    mp4_url: str = ""
    file_size_bytes: int = 0
    duration_seconds: int = 0
    started_at: int = 0
    format: str = "hls"


# ── Recorder Manager ──


class RecorderManager:
    """Manages HLS recording jobs (mock)."""

    def __init__(self, recording_dir: str = "/data/recordings") -> None:
        self._recording_dir = recording_dir
        self._recordings: dict[str, RecordingState] = {}

    def start_recording(
        self,
        live_room_id: str,
        fmt: str = "hls",
    ) -> RecordingState:
        """Start recording a live stream.

        Args:
            live_room_id: Identifier for the live room.
            fmt: Recording format ("hls" or "mp4").

        Returns:
            The newly created RecordingState.
        """
        recording_id = f"rec-{uuid.uuid4().hex[:12]}"
        hls_url = f"{self._recording_dir}/{live_room_id}/{recording_id}/index.m3u8"
        mp4_url = f"{self._recording_dir}/{live_room_id}/{recording_id}.mp4"

        recording = RecordingState(
            recording_id=recording_id,
            live_room_id=live_room_id,
            status=RecordingStatus.RECORDING,
            hls_url=hls_url,
            mp4_url=mp4_url,
            started_at=int(time.time() * 1000),
            format=fmt,
        )

        self._recordings[recording_id] = recording
        logger.info(
            "recorder.started",
            recording_id=recording_id,
            live_room_id=live_room_id,
            format=fmt,
        )

        return recording

    def stop_recording(self, recording_id: str) -> RecordingState | None:
        """Stop an active recording.

        Args:
            recording_id: The recording to stop.

        Returns:
            The final RecordingState, or None if not found.
        """
        recording = self._recordings.get(recording_id)
        if not recording:
            logger.warning("recorder.not_found", recording_id=recording_id)
            return None

        elapsed_ms = int(time.time() * 1000) - recording.started_at
        duration_seconds = max(1, elapsed_ms // 1000)

        recording.status = RecordingStatus.COMPLETED
        recording.duration_seconds = duration_seconds
        recording.file_size_bytes = duration_seconds * 500_000  # ~500 KB/s mock

        logger.info(
            "recorder.stopped",
            recording_id=recording_id,
            duration_seconds=duration_seconds,
            file_size_bytes=recording.file_size_bytes,
        )

        return recording

    def get_recording(self, recording_id: str) -> RecordingState | None:
        """Get a recording by ID."""
        return self._recordings.get(recording_id)
