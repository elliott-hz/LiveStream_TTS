"""
Mock transcode job management.

In production this would submit jobs to FFmpeg (possibly GPU-accelerated)
to transcode recorded streams to different resolutions/bitrates. Here we
simulate the job lifecycle in memory.

Transcode lifecycle:
  QUEUED -> PROCESSING -> COMPLETED / FAILED
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from libs.common.logging import get_logger

logger = get_logger(__name__)


# ── Transcode Status ──


class TranscodeStatus(IntEnum):
    UNSPECIFIED = 0
    QUEUED = 1
    PROCESSING = 2
    COMPLETED = 3
    FAILED = 4


# ── Data Models ──


@dataclass
class TranscodeJobState:
    """In-memory state for a transcode job."""

    job_id: str
    status: TranscodeStatus = TranscodeStatus.UNSPECIFIED
    input_url: str = ""
    output_url: str = ""
    progress_percent: int = 0
    target_width: int = 1920
    target_height: int = 1080
    target_fps: int = 30
    target_bitrate_kbps: int = 5000
    target_format: str = "mp4"
    created_at: int = 0


# ── Transcode Manager ──


class TranscodeManager:
    """Manages transcode jobs (mock)."""

    def __init__(self, queue_size: int = 10) -> None:
        self._queue_size = queue_size
        self._jobs: dict[str, TranscodeJobState] = {}

    def create_job(
        self,
        recording_id: str,
        target_width: int = 1920,
        target_height: int = 1080,
        target_fps: int = 30,
        target_bitrate_kbps: int = 5000,
        target_format: str = "mp4",
    ) -> TranscodeJobState:
        """Create a transcode job for a recording.

        Args:
            recording_id: Source recording identifier.
            target_width: Output video width.
            target_height: Output video height.
            target_fps: Output frames per second.
            target_bitrate_kbps: Output bitrate in kbps.
            target_format: Output container format.

        Returns:
            The newly created TranscodeJobState.
        """
        job_id = f"tc-{uuid.uuid4().hex[:12]}"
        input_url = f"/data/recordings/{recording_id}/index.m3u8"
        output_url = f"/data/recordings/{recording_id}/transcoded_{target_width}p.{target_format}"

        job = TranscodeJobState(
            job_id=job_id,
            status=TranscodeStatus.QUEUED,
            input_url=input_url,
            output_url=output_url,
            target_width=target_width,
            target_height=target_height,
            target_fps=target_fps,
            target_bitrate_kbps=target_bitrate_kbps,
            target_format=target_format,
            created_at=int(time.time() * 1000),
        )

        self._jobs[job_id] = job

        # Simulate immediate processing start
        self._simulate_progress(job)

        logger.info(
            "transcoder.job_created",
            job_id=job_id,
            recording_id=recording_id,
            target=f"{target_width}x{target_height}@{target_fps}fps",
        )

        return job

    def get_job(self, job_id: str) -> TranscodeJobState | None:
        """Get a transcode job by ID."""
        return self._jobs.get(job_id)

    def _simulate_progress(self, job: TranscodeJobState) -> None:
        """Simulate transcode job progress."""
        job.status = TranscodeStatus.PROCESSING
        # Simulate 100% progress to indicate "completed" in mock
        job.progress_percent = 100
        job.status = TranscodeStatus.COMPLETED
