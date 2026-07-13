"""
M8 — Audio Post Processing (DSP)
POC: 简化实现 — Normalize（响度归一化）+ Silence Trim（静音裁剪）。
"""

import logging
import math
import struct
from typing import AsyncGenerator

logger = logging.getLogger("M8.DSP")


SAMPLE_RATE = 16000
TARGET_RMS = 0.3        # 目标 RMS 值（0.0 ~ 1.0）
SILENCE_THRESHOLD = 0.02  # 静音阈值


class DSP:
    """
    音频后处理。
    POC: 逐 chunk 处理。Normailze + 首尾静音裁剪。
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self._first_non_silence = False
        self._pre_silence_chunks = []

    def _pcm_bytes_to_samples(self, data: bytes) -> list[int]:
        """PCM bytes → int samples (signed 16-bit LE)。"""
        count = len(data) // 2
        return list(struct.unpack(f"<{count}h", data))

    def _samples_to_pcm_bytes(self, samples: list[int]) -> bytes:
        """int samples → PCM bytes。"""
        return struct.pack(f"<{len(samples)}h", *samples)

    def _rms(self, samples: list[int]) -> float:
        """计算 RMS。"""
        if not samples:
            return 0.0
        sum_sq = sum(s * s for s in samples)
        return math.sqrt(sum_sq / len(samples)) / 32768.0

    def _normalize_chunk(self, samples: list[int]) -> list[int]:
        """响度归一化。"""
        rms = self._rms(samples)
        if rms < 0.001:
            return samples
        gain = TARGET_RMS / rms
        return [max(-32768, min(32767, int(s * gain))) for s in samples]

    def process_chunk(self, pcm_bytes: bytes) -> bytes:
        """
        处理单个 PCM Chunk（20ms）。
        """
        if not pcm_bytes:
            return b""

        samples = self._pcm_bytes_to_samples(pcm_bytes)
        rms_before = self._rms(samples)

        # Silence Trim（裁剪首部静音）
        if not self._first_non_silence:
            if rms_before < SILENCE_THRESHOLD:
                self._pre_silence_chunks.append(len(samples))
                logger.info(f"  [DSP] Trimmed silence chunk #{len(self._pre_silence_chunks)} (RMS={rms_before:.4f})")
                return b""
            self._first_non_silence = True
            trimmed_count = len(self._pre_silence_chunks)
            if trimmed_count > 0:
                logger.info(f"  [DSP] Trimmed {trimmed_count} leading silence chunks")
            self._pre_silence_chunks = []

        # Normalize
        samples = self._normalize_chunk(samples)
        rms_after = self._rms(samples)

        result = self._samples_to_pcm_bytes(samples)
        logger.info(f"  [DSP] Chunk: {len(pcm_bytes)}B → {len(result)}B, RMS {rms_before:.4f} → {rms_after:.4f}")
        return result

    def reset(self):
        """重置 DSP 状态（每个新请求调用）。"""
        self._first_non_silence = False
        self._pre_silence_chunks = []
