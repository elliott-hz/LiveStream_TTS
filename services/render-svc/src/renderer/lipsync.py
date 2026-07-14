"""
Mock Wav2Lip — generate blendshape weights from audio input.

In production this would use a Wav2Lip / TalkNet model to predict
mouth-articulation blendshape weights from audio frames. Here we
return random weights as a placeholder.

Blendshape schema (ARKit-compatible 52-shape basis):
  jawOpen, jawLeft, jawForward, mouthOpen, mouthFunnel, pucker, ...
"""

from __future__ import annotations

import hashlib
import math
import struct
from typing import Sequence

import numpy as np

from libs.common.logging import get_logger

logger = get_logger(__name__)

# ── Constants ──

NUM_BLENDSHAPES = 52
SAMPLE_RATE = 16000
FRAME_DURATION_SEC = 0.04  # 25 fps = 40ms frames
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_DURATION_SEC)


# ── Public API ──


def predict_blendshapes(
    audio_data: bytes,
    sample_rate: int = SAMPLE_RATE,
    avatar_id: str | None = None,
) -> tuple[np.ndarray, int]:
    """Predict blendshape weights from audio data.

    Args:
        audio_data: Raw PCM16 audio bytes.
        sample_rate: Sample rate of the audio (Hz).
        avatar_id: Optional avatar identifier (unused in mock).

    Returns:
        A tuple of (weights_matrix, frame_count) where weights_matrix
        has shape (frame_count, NUM_BLENDSHAPES) with values in [0, 1].
    """
    num_samples = len(audio_data) // 2  # PCM16 = 2 bytes per sample
    num_frames = max(1, math.ceil(num_samples / FRAME_SAMPLES))

    logger.info(
        "lipsync.predict",
        audio_bytes=len(audio_data),
        sample_rate=sample_rate,
        num_frames=num_frames,
        avatar_id=avatar_id or "unknown",
    )

    # Derive a deterministic seed from the audio content so the same
    # audio produces the same blendshape sequence (repeatable mock).
    seed = int(hashlib.md5(audio_data[:4096]).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)

    # Generate smooth-ish random blendshape weights
    weights = np.zeros((num_frames, NUM_BLENDSHAPES), dtype=np.float32)
    for f in range(num_frames):
        # Base random vector
        base = rng.random(NUM_BLENDSHAPES, dtype=np.float32)
        # Jaw / mouth shapes get higher weights for speech activity
        # Simulate speech envelope: vary per frame
        envelope = 0.3 + 0.7 * abs(math.sin(f * 0.15))
        weights[f] = base * envelope

    # Clamp to [0, 1]
    np.clip(weights, 0.0, 1.0, out=weights)

    return weights, num_frames


def extract_rms(audio_data: bytes, sample_rate: int = SAMPLE_RATE) -> list[float]:
    """Extract RMS energy per frame for visualisation (helper).

    Args:
        audio_data: Raw PCM16 audio bytes.
        sample_rate: Sample rate of the audio (Hz).

    Returns:
        List of RMS values per 40 ms frame.
    """
    samples = struct.unpack(f"<{len(audio_data) // 2}h", audio_data)
    num_frames = max(1, len(samples) // FRAME_SAMPLES)

    rms_values: list[float] = []
    for f in range(num_frames):
        start = f * FRAME_SAMPLES
        end = start + FRAME_SAMPLES
        frame = samples[start:end]
        if not frame:
            continue
        rms = math.sqrt(sum(s * s for s in frame) / len(frame))
        rms_values.append(rms / 32768.0)  # Normalise to [0, 1]

    return rms_values
