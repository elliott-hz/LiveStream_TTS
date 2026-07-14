"""
M7 — Streaming TTS Engine
POC: Mock 实现 — 正弦波。无外部依赖。
"""

import logging
import math
import struct
from typing import Callable, Optional

from .linguistic_engine import LinguisticFeatures
from .emotion_engine import EmotionTag

logger = logging.getLogger(__name__)


CHUNK_DURATION_SEC = 0.02   # 20ms per chunk
SAMPLE_RATE = 16000
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION_SEC)  # 320 samples


# 情感 → 音频参数
EMOTION_AUDIO_MAP = {
    "neutral": {"freq": 220, "volume": 0.6},
    "happy":   {"freq": 330, "volume": 0.8},
    "sad":     {"freq": 180, "volume": 0.5},
    "excited": {"freq": 440, "volume": 0.9},
    "calm":    {"freq": 200, "volume": 0.4},
}


class TTSResult:
    """合成结果。"""
    def __init__(self, request_id: str, total_chunks: int, duration_ms: int):
        self.request_id = request_id
        self.total_chunks = total_chunks
        self.duration_ms = duration_ms


class TTSEngine:
    """
    流式 TTS 引擎。
    POC Mock: 根据 Emotion 生成不同频率的正弦波。
      - Emotion 影响频率（pitch）和音量
      - 停顿位置插入静音
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE, chunk_size: int = CHUNK_SIZE):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self._phase = 0.0

    def synthesize_stream(
        self,
        request_id: str,
        features: LinguisticFeatures,
        emotion: EmotionTag,
        speed: float,
        on_chunk: Callable,
        on_complete: Callable,
        on_error: Callable,
    ):
        """流式合成。逐 chunk 回调。"""
        logger.info("╔═══════════════════════════════════════════")
        logger.info(f"║ REQUEST: {request_id}")
        logger.info(f"║ EMOTION: {emotion.emotion}, SPEED: {speed}")
        logger.info(f"║ PHONEMES: {len(features.phonemes)}")

        try:
            audio_cfg = EMOTION_AUDIO_MAP.get(emotion.emotion, EMOTION_AUDIO_MAP["neutral"])
            freq = audio_cfg["freq"]
            volume = audio_cfg["volume"]
            logger.info(f"║ WAVE: freq={freq}Hz, volume={volume}")

            # 根据音素数量计算总时长
            phoneme_count = len(features.phonemes) or 1
            total_duration_sec = phoneme_count * 0.08 / max(speed, 0.1)
            total_pause_sec = sum(p["duration_ms"] for p in features.pause_positions) / 1000.0
            total_duration_sec += total_pause_sec
            total_chunks = max(int(total_duration_sec / CHUNK_DURATION_SEC), 1)
            logger.info(f"║ DURATION: {total_duration_sec:.1f}s → {total_chunks} chunks")

            # 停顿索引集合
            pause_indices = {p["after_phoneme_index"] for p in features.pause_positions}

            for seq in range(total_chunks):
                current_phoneme = int(seq * phoneme_count / total_chunks)
                if current_phoneme in pause_indices:
                    samples = [0] * self.chunk_size
                else:
                    samples = []
                    for i in range(self.chunk_size):
                        value = int(volume * 16000 * math.sin(2 * math.pi * freq * self._phase / self.sample_rate))
                        samples.append(max(-32768, min(32767, value)))
                        self._phase += 1
                pcm = struct.pack(f"<{self.chunk_size}h", *samples)
                on_chunk(request_id, seq, pcm)

            duration_ms = int(total_chunks * CHUNK_DURATION_SEC * 1000)
            logger.info(f"║ DONE: {total_chunks} chunks, {duration_ms}ms")
            logger.info("╚═══════════════════════════════════════════")
            on_complete(TTSResult(request_id, total_chunks, duration_ms))

        except Exception as e:
            logger.error(f"TTS Engine error: {e}", exc_info=True)
            on_error(4001, f"TTS Engine inference failed: {e}")
