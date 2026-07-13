"""
M7 — Streaming TTS Engine
POC: Mock 实现 — 用正弦波模拟 PCM 输出，证明全管线可通。
     替换为 CosyVoice2 / FishSpeech 即可接入真实 TTS。
"""

import math
import struct
from typing import Callable, Optional

from .linguistic_engine import LinguisticFeatures
from .emotion_engine import EmotionTag


CHUNK_DURATION_SEC = 0.02   # 20ms per chunk
SAMPLE_RATE = 16000
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION_SEC)  # 320 samples


class TTSResult:
    """合成结果，携带统计信息供回调。"""
    def __init__(self, request_id: str, total_chunks: int, duration_ms: int):
        self.request_id = request_id
        self.total_chunks = total_chunks
        self.duration_ms = duration_ms


class TTSEngine:
    """
    流式 TTS 引擎。

    POC Mock: 根据 LinguisticFeatures 生成正弦波 PCM。
      - 音素越多 → 音频越长
      - Emotion 影响频率（pitch）和音量
      - 停顿位置插入静音

    替换为真实模型时，只需重写 _infer_chunk() 方法。
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE, chunk_size: int = CHUNK_SIZE):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self._phase = 0.0  # 正弦波相位（跨 chunk 延续）

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
        """
        流式合成。逐 chunk 回调。
        Args:
            request_id: 请求标识
            features: M4 输出的语言学特征
            emotion: M5 输出的情感标签
            speed: 语速倍率
            on_chunk: func(request_id, sequence, pcm_bytes) → None
            on_complete: func(TTSResult) → None
            on_error: func(error_code, message) → None
        """
        try:
            total_duration_ms = 0
            total_chunks = 0

            # 根据音素 + 停顿计算总时长
            phoneme_count = len(features.phonemes)
            total_duration_sec = phoneme_count * 0.08 / max(speed, 0.1)
            total_pause_sec = sum(p["duration_ms"] for p in features.pause_positions) / 1000.0
            total_duration_sec += total_pause_sec

            total_chunks = int(total_duration_sec / CHUNK_DURATION_SEC)
            if total_chunks < 1:
                total_chunks = 1

            # 情感 → 音频参数
            emotion_map = {
                "neutral": (220, 0.6), "happy": (330, 0.8),
                "sad": (180, 0.5), "excited": (440, 0.9), "calm": (200, 0.4),
            }
            freq, volume = emotion_map.get(emotion.emotion, (220, 0.6))

            # 停顿索引集合（用于插入静音）
            pause_indices = {p["after_phoneme_index"] for p in features.pause_positions}

            for seq in range(total_chunks):
                # 判断当前 chunk 是否在停顿区域内
                current_phoneme = int(seq * phoneme_count / max(total_chunks, 1))
                if current_phoneme in pause_indices:
                    # 静音 chunk
                    pcm = struct.pack(f"<{self.chunk_size}h", *([0] * self.chunk_size))
                else:
                    # 正弦波 chunk
                    samples = []
                    for i in range(self.chunk_size):
                        value = int(volume * 16000 * math.sin(2 * math.pi * freq * self._phase / self.sample_rate))
                        samples.append(max(-32768, min(32767, value)))
                        self._phase += 1
                    pcm = struct.pack(f"<{self.chunk_size}h", *samples)

                # 回调 M8 DSP 处理后的数据
                on_chunk(request_id, seq, pcm)
                total_duration_ms = int((seq + 1) * CHUNK_DURATION_SEC * 1000)

            on_complete(TTSResult(
                request_id=request_id,
                total_chunks=total_chunks,
                duration_ms=total_duration_ms,
            ))

        except Exception as e:
            on_error(4001, f"TTS Engine inference failed: {e}")
