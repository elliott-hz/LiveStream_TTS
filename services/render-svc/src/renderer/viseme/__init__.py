"""
2D Viseme Engine — Phoneme-to-mouth-shape mapping for lip-sync rendering.

Replaces Wav2Lip (GPU) with a lightweight CPU-based approach for Phase 2.
Maps audio energy + phonemes to 12 predefined viseme (mouth shape) indices
with smooth interpolation.

12 Viseme shapes (ARKit-compatible subset):
  0 — 闭嘴 (closed / rest)
  1 — 轻微张开 (slight open / "schwa")
  2 — A / 大张开 (wide open / "ah")
  3 — E (wide / "eh")
  4 — I (grin / "ee")
  5 — O (rounded / "oh")
  6 — U (tight rounded / "oo")
  7 — F-V 咬唇 (lip bite / "f", "v")
  8 — L-舌尖 (tongue tip / "l", "th")
  9 — M-B-P 闭唇 (pressed lips / "m", "b", "p")
  10 — W-Q 圆唇 (tight round / "w", "q")
  11 — 中等张开 (medium open / default speaking)

Architecture:
    TTS Audio PCM → RMS Energy per frame + Phoneme timeline
                 → Viseme Index per frame (with interpolation)
                 → Blendshape weights (52-dim) → Compositor
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass

from libs.common.logging import get_logger

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────
NUM_VISEMES = 12
NUM_BLENDSHAPES = 52
SAMPLE_RATE = 16000
FRAME_DURATION_SEC = 0.04  # 25 fps
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_DURATION_SEC)  # 640 samples

# ── Phoneme → Viseme Mapping ─────────────────────────────────

# Maps Chinese phonemes (Bopomofo / Pinyin) to viseme indices
# Based on standard viseme-phoneme correspondences
PHONEME_TO_VISEME: dict[str, int] = {
    # Vowels
    "a": 2, "ā": 2, "á": 2, "ǎ": 2, "à": 2,  # A → 大张开
    "e": 3, "ē": 3, "é": 3, "ě": 3, "è": 3,  # E → wide
    "i": 4, "ī": 4, "í": 4, "ǐ": 4, "ì": 4,  # I → grin
    "o": 5, "ō": 5, "ó": 5, "ǒ": 5, "ò": 5,  # O → rounded
    "u": 6, "ū": 6, "ú": 6, "ǔ": 6, "ù": 6,  # U → tight rounded
    "ü": 6, "ǖ": 6, "ǘ": 6, "ǚ": 6, "ǜ": 6,  # ü → U-like

    # Consonants — bilabial (closed/pressed lips)
    "b": 9, "p": 9, "m": 9,  # M-B-P → 闭唇

    # Consonants — labiodental (lip bite)
    "f": 7,  # F-V → 咬唇

    # Consonants — alveolar / tongue tip
    "l": 8, "n": 8, "d": 8, "t": 8,  # L → 舌尖

    # Consonants — rounded
    "w": 10, "y": 10,  # W-Q → 圆唇

    # Consonants — default speaking position
    "g": 11, "k": 11, "h": 11,  # velar → medium open
    "j": 11, "q": 11, "x": 11,  # palatal → medium open
    "z": 11, "c": 11, "s": 11,  # dental → medium open
    "zh": 11, "ch": 11, "sh": 11, "r": 11,  # retroflex → medium open

    # Silence / pause
    "sil": 0, "sp": 0, "": 0,
}

# Default viseme for unknown phonemes
DEFAULT_VISEME = 11  # medium open


@dataclass
class VisemeFrame:
    """A single viseme frame at 25fps."""
    index: int          # Viseme index 0-11
    jaw_open: float     # 0.0 (closed) – 1.0 (fully open)
    lip_round: float    # 0.0 (neutral) – 1.0 (rounded)
    lip_bite: float     # 0.0 (neutral) – 1.0 (biting lower lip)
    energy: float       # RMS audio energy


class VisemeEngine:
    """2D Viseme engine — converts audio + phonemes to mouth shape frames.

    Usage::

        engine = VisemeEngine()
        frames = engine.synthesize(audio_bytes, phonemes, durations_ms)
        # → List[VisemeFrame] at 25fps
    """

    def __init__(self, fps: int = 25) -> None:
        self.fps = fps
        self.frame_duration = 1.0 / fps
        self.frame_samples = int(SAMPLE_RATE * self.frame_duration)

    def synthesize(
        self,
        audio_data: bytes,
        phonemes: list[str] | None = None,
        durations_ms: list[int] | None = None,
    ) -> list[VisemeFrame]:
        """Convert audio + phoneme timeline to viseme frames.

        Args:
            audio_data: PCM16 audio bytes at 16kHz.
            phonemes: Optional list of phoneme strings (Bopomofo/Pinyin).
            durations_ms: Optional phoneme durations in milliseconds.

        Returns:
            List of VisemeFrame at 25fps covering the total audio duration.
        """
        # 1. Compute audio energy per frame
        energies = _extract_energy_frames(audio_data, self.frame_samples)
        num_frames = len(energies)

        # 2. Build phoneme timeline if provided
        viseme_timeline: list[tuple[int, int, int]] = []  # (start_frame, end_frame, viseme_idx)
        if phonemes:
            viseme_timeline = self._build_timeline(phonemes, durations_ms or [], num_frames)

        # 3. Generate viseme frames with interpolation
        frames: list[VisemeFrame] = []
        for f in range(num_frames):
            energy = energies[f]

            if viseme_timeline:
                # Find active viseme for this frame
                viseme_idx = self._find_viseme_at_frame(f, viseme_timeline)
            else:
                # No phonemes — use energy-driven viseme mapping
                viseme_idx = _energy_to_viseme(energy)

            # Compute shape parameters from viseme index + energy
            jaw_open, lip_round, lip_bite = _viseme_params(viseme_idx, energy)

            frames.append(VisemeFrame(
                index=viseme_idx,
                jaw_open=jaw_open,
                lip_round=lip_round,
                lip_bite=lip_bite,
                energy=energy,
            ))

        logger.debug(
            "viseme.synthesized",
            num_frames=num_frames,
            num_phonemes=len(phonemes) if phonemes else 0,
            avg_energy=round(sum(energies) / max(len(energies), 1), 4),
        )

        return frames

    def to_blendshape_weights(self, frames: list[VisemeFrame]) -> list[list[float]]:
        """Convert viseme frames to 52-dim ARKit-compatible blendshape weights.

        Each frame becomes a 52-element list of floats in [0, 1].
        Only mouth-related shapes are activated; the rest remain 0.
        """
        weights_list: list[list[float]] = []

        for frame in frames:
            w = [0.0] * NUM_BLENDSHAPES

            # ARKit blendshape indices for mouth shapes
            # jawOpen = 0, mouthOpen = 3, mouthPucker = 5,
            # mouthFunnel = 6, mouthSmile = 9, mouthFrown = 12,
            # mouthDimple = 15, mouthPress = 21, ...
            w[0] = frame.jaw_open           # jawOpen
            w[3] = frame.jaw_open * 0.8     # mouthOpen
            w[5] = frame.lip_round * 0.7    # mouthPucker
            w[6] = frame.lip_round * 0.5    # mouthFunnel
            w[9] = frame.jaw_open * 0.3     # mouthSmile (slight smile when speaking)
            w[21] = frame.lip_bite * 0.8    # mouthPress (lip bite)
            w[26] = frame.jaw_open * 0.2    # mouthStretch
            w[37] = frame.lip_bite * 0.6    # mouthLowerDown

            # Clamp
            for i in range(NUM_BLENDSHAPES):
                w[i] = max(0.0, min(1.0, w[i]))

            weights_list.append(w)

        return weights_list

    @staticmethod
    def _build_timeline(
        phonemes: list[str],
        durations_ms: list[int],
        num_frames: int,
    ) -> list[tuple[int, int, int]]:
        """Build a viseme timeline from phoneme + duration data."""
        timeline: list[tuple[int, int, int]] = []
        current_ms = 0.0
        frame_ms = FRAME_DURATION_SEC * 1000  # 40ms per frame at 25fps

        for i, phoneme in enumerate(phonemes):
            dur = durations_ms[i] if i < len(durations_ms) else 80
            start_frame = int(current_ms / frame_ms)
            end_frame = int((current_ms + dur) / frame_ms)
            viseme_idx = PHONEME_TO_VISEME.get(phoneme.lower(), DEFAULT_VISEME)
            timeline.append((start_frame, end_frame, viseme_idx))
            current_ms += dur

        return timeline

    @staticmethod
    def _find_viseme_at_frame(
        frame: int,
        timeline: list[tuple[int, int, int]],
    ) -> int:
        """Find the active viseme index for a given frame."""
        for start, end, idx in timeline:
            if start <= frame <= end:
                return idx
        # Default: slight open when speaking
        return 1


# ── Helpers ─────────────────────────────────────────────────


def _extract_energy_frames(audio_data: bytes, frame_samples: int) -> list[float]:
    """Extract RMS energy per frame from PCM16 audio."""
    if len(audio_data) < 4:
        return [0.0]

    num_samples = len(audio_data) // 2
    samples = struct.unpack(f"<{num_samples}h", audio_data)
    num_frames = max(1, len(samples) // frame_samples)

    energies: list[float] = []
    for f in range(num_frames):
        start = f * frame_samples
        end = min(start + frame_samples, len(samples))
        frame = samples[start:end]
        if not frame:
            energies.append(0.0)
            continue
        rms = math.sqrt(sum(s * s for s in frame) / len(frame))
        # Normalize: typical speech RMS is 2000-8000 in 16-bit
        energies.append(min(1.0, rms / 4000.0))

    return energies


def _energy_to_viseme(energy: float) -> int:
    """Map audio energy to a viseme index (when no phoneme data available)."""
    if energy < 0.02:
        return 0   # silence → closed mouth
    if energy < 0.08:
        return 1   # very quiet → slight open
    if energy < 0.2:
        return 11  # quiet → medium open
    if energy < 0.4:
        return 2   # normal → wide open
    return 2       # loud → wide open


def _viseme_params(idx: int, energy: float) -> tuple[float, float, float]:
    """Compute (jaw_open, lip_round, lip_bite) from viseme index + energy.

    Energy modulates the intensity of the mouth shape.
    """
    # Base parameters per viseme
    _BASE_PARAMS: dict[int, tuple[float, float, float]] = {
        0:  (0.0, 0.0, 0.0),    # 闭嘴
        1:  (0.2, 0.0, 0.0),    # 轻微张开
        2:  (0.8, 0.0, 0.0),    # A / 大张开
        3:  (0.5, 0.0, 0.1),    # E
        4:  (0.3, 0.0, 0.0),    # I (grin)
        5:  (0.4, 0.6, 0.0),    # O (rounded)
        6:  (0.2, 0.8, 0.0),    # U (tight round)
        7:  (0.1, 0.0, 0.7),    # F-V 咬唇
        8:  (0.3, 0.0, 0.0),    # L 舌尖
        9:  (0.05, 0.0, 0.0),   # M-B-P 闭唇
        10: (0.2, 0.9, 0.0),    # W-Q 圆唇
        11: (0.4, 0.0, 0.0),    # 中等张开 (default)
    }

    jaw_open, lip_round, lip_bite = _BASE_PARAMS.get(idx, (0.3, 0.0, 0.0))

    # Modulate by energy: more energy = wider mouth opening
    energy_scale = min(1.0, 0.4 + energy * 1.5)

    return (
        round(min(1.0, jaw_open * energy_scale), 4),
        round(lip_round, 4),
        round(min(1.0, lip_bite * energy_scale), 4),
    )
