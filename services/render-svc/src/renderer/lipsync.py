"""
Lipsync — Generate blendshape weights from TTS audio.

Phase 2: Uses 2D Viseme engine (CPU-based phoneme→mouth-shape mapping).
Phase 3: Upgradable to Wav2Lip (GPU-based, photorealistic).

Blendshape schema (ARKit-compatible 52-shape basis):
  jawOpen, jawLeft, jawForward, mouthOpen, mouthFunnel, pucker, ...
"""

from __future__ import annotations

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

# Engine selection (lazy init)
_viseme_engine = None


def _get_viseme_engine():
    """Lazy-init the Viseme engine singleton."""
    global _viseme_engine
    if _viseme_engine is None:
        from .viseme import VisemeEngine
        _viseme_engine = VisemeEngine(fps=25)
    return _viseme_engine


# ── Public API ──


def predict_blendshapes(
    audio_data: bytes,
    sample_rate: int = SAMPLE_RATE,
    avatar_id: str | None = None,
    phonemes: list[str] | None = None,
    durations_ms: list[int] | None = None,
) -> tuple[np.ndarray, int]:
    """Predict blendshape weights from audio + optional phoneme data.

    Uses 2D Viseme engine for Phase 2. Falls back to energy-based
    random blendshapes if viseme engine is unavailable.

    Args:
        audio_data: Raw PCM16 audio bytes.
        sample_rate: Sample rate of the audio (Hz).
        avatar_id: Optional avatar identifier (unused in 2D mode).
        phonemes: Optional phoneme list for accurate viseme mapping.
        durations_ms: Optional phoneme durations for accurate timeline.

    Returns:
        A tuple of (weights_matrix, frame_count) where weights_matrix
        has shape (frame_count, NUM_BLENDSHAPES) with values in [0, 1].
    """
    num_samples = len(audio_data) // 2
    num_frames = max(1, math.ceil(num_samples / FRAME_SAMPLES))

    logger.info(
        "lipsync.predict",
        audio_bytes=len(audio_data),
        sample_rate=sample_rate,
        num_frames=num_frames,
        has_phonemes=phonemes is not None and len(phonemes) > 0 if phonemes else False,
        avatar_id=avatar_id or "unknown",
    )

    try:
        engine = _get_viseme_engine()
        viseme_frames = engine.synthesize(
            audio_data=audio_data,
            phonemes=phonemes,
            durations_ms=durations_ms,
        )

        # Convert viseme frames to blendshape weights
        weights_list = engine.to_blendshape_weights(viseme_frames)
        num_frames = len(weights_list)

        weights = np.zeros((num_frames, NUM_BLENDSHAPES), dtype=np.float32)
        for f, w in enumerate(weights_list):
            if f < num_frames:
                weights[f] = w

        # Smooth across consecutive frames (simple moving average, window=3)
        if num_frames > 2:
            smoothed = weights.copy()
            for f in range(1, num_frames - 1):
                smoothed[f] = (weights[f - 1] + weights[f] + weights[f + 1]) / 3.0
            weights = smoothed

        np.clip(weights, 0.0, 1.0, out=weights)

        return weights, num_frames

    except Exception as e:
        logger.warning("viseme.engine_failed", error=str(e), hint="Using energy-based fallback")
        return _predict_blendshapes_energy_fallback(audio_data, sample_rate)


def _predict_blendshapes_energy_fallback(
    audio_data: bytes,
    sample_rate: int = SAMPLE_RATE,
) -> tuple[np.ndarray, int]:
    """Energy-based blendshape fallback (when Viseme engine is unavailable)."""
    num_samples = len(audio_data) // 2
    num_frames = max(1, math.ceil(num_samples / FRAME_SAMPLES))

    energies = extract_rms(audio_data, sample_rate)

    weights = np.zeros((num_frames, NUM_BLENDSHAPES), dtype=np.float32)
    for f in range(num_frames):
        energy = energies[f] if f < len(energies) else energies[-1] if energies else 0.1

        # Energy drives mouth openness
        w = [0.0] * NUM_BLENDSHAPES
        w[0] = min(1.0, energy * 2.0)    # jawOpen
        w[3] = min(1.0, energy * 1.8)    # mouthOpen
        w[9] = min(1.0, energy * 0.8)    # mouthSmile
        w[26] = min(1.0, energy * 0.5)   # mouthStretch
        weights[f] = w

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
    num_samples = len(audio_data) // 2
    if num_samples < 2:
        return [0.0]

    samples = struct.unpack(f"<{num_samples}h", audio_data)
    num_frames = max(1, len(samples) // FRAME_SAMPLES)

    rms_values: list[float] = []
    for f in range(num_frames):
        start = f * FRAME_SAMPLES
        end = start + FRAME_SAMPLES
        frame = samples[start:end]
        if not frame:
            continue
        rms = math.sqrt(sum(s * s for s in frame) / len(frame))
        rms_values.append(rms / 32768.0)

    return rms_values
