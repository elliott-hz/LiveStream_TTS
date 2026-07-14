"""
Mock FFmpeg compositor — compose video frames from avatar + overlays.

In production this would invoke FFmpeg (or a GPU-accelerated compositor)
to render the final video frame by combining:

  1. The digital human avatar frame (rendered by Wav2Lip or similar)
  2. Background image / video
  3. Overlay layers (product cards, price tags, etc.)
  4. Text / captions

Here we return dummy frame bytes as a placeholder and log the composition
parameters.
"""

from __future__ import annotations

import hashlib
import struct
import time
from typing import Sequence

from libs.common.logging import get_logger

from src.renderer.overlays import OverlayDefinition, render_overlay

logger = get_logger(__name__)

# ── Constants ──

DEFAULT_FRAME_WIDTH = 1920
DEFAULT_FRAME_HEIGHT = 1080
DEFAULT_FPS = 30
FRAME_HEADER_SIZE = 64  # Placeholder header bytes per frame


# ── Public API ──


def compose_frame(
    avatar_id: str,
    frame_number: int,
    width: int = DEFAULT_FRAME_WIDTH,
    height: int = DEFAULT_FRAME_HEIGHT,
    fps: int = DEFAULT_FPS,
    background_id: str | None = None,
    overlays: Sequence[OverlayDefinition] | None = None,
    blendshape_weights: bytes | None = None,
) -> bytes:
    """Compose a single video frame.

    Args:
        avatar_id: Identifier of the digital human avatar.
        frame_number: Sequential frame number.
        width: Frame width in pixels.
        height: Frame height in pixels.
        fps: Target frames per second.
        background_id: Optional background scene identifier.
        overlays: Sequence of overlay definitions to render on the frame.
        blendshape_weights: Serialised blendshape weights (52 floats as bytes).

    Returns:
        Serialised frame bytes: a small header followed by dummy pixel data.
    """
    overlay_list = list(overlays) if overlays else []

    logger.debug(
        "compositor.compose_frame",
        avatar_id=avatar_id,
        frame_number=frame_number,
        width=width,
        height=height,
        overlays=len(overlay_list),
        background_id=background_id or "default",
    )

    # ── Simulate render overhead ──
    # Derive pixel content from frame number + avatar_id for determinism
    seed_str = f"{avatar_id}:{frame_number}"
    digest = hashlib.md5(seed_str.encode()).digest()

    # Build a dummy frame payload:
    #   [header] + [dummy pixel data]
    header = struct.pack(
        ">IIIII",
        frame_number,
        width,
        height,
        fps,
        int(time.time()),
    )
    # Pad header to FRAME_HEADER_SIZE bytes
    header = header.ljust(FRAME_HEADER_SIZE, b"\x00")

    # Dummy pixel data: 64 bytes of deterministic content
    pixel_data = digest * 4  # 64 bytes

    frame_bytes = header + pixel_data
    return frame_bytes


def compose_frames_batch(
    avatar_id: str,
    start_frame: int,
    count: int,
    width: int = DEFAULT_FRAME_WIDTH,
    height: int = DEFAULT_FRAME_HEIGHT,
    fps: int = DEFAULT_FPS,
    background_id: str | None = None,
    overlays: Sequence[OverlayDefinition] | None = None,
) -> bytes:
    """Compose a batch of consecutive frames.

    Returns the concatenation of all frame byte payloads.
    """
    frames = bytearray()
    for i in range(count):
        frame = compose_frame(
            avatar_id=avatar_id,
            frame_number=start_frame + i,
            width=width,
            height=height,
            fps=fps,
            background_id=background_id,
            overlays=overlays,
        )
        frames.extend(frame)
    return bytes(frames)
