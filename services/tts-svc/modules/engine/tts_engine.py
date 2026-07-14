"""
M7 — Streaming TTS Engine

Dual-backend architecture:
  - ``mock`` — sine-wave generator (no external API, offline debugging)
  - ``cloud`` — Alibaba Cloud NLS (CosyVoice) streaming TTS API

Same callback interface (on_chunk / on_complete / on_error) regardless
of backend, so the gRPC service layer is completely unaffected.
"""

import asyncio
import math
import struct
from collections.abc import Callable

from libs.common.logging import get_logger
from modules.emotion.emotion_engine import EmotionTag
from modules.engine.cloud_tts_client import (
    CloudTTSClient,
    CloudTTSConfig,
    CloudTTSResult,
)
from modules.linguistic.linguistic_engine import LinguisticFeatures

logger = get_logger(__name__)


CHUNK_DURATION_SEC = 0.02   # 20ms per chunk
SAMPLE_RATE = 16000
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION_SEC)  # 320 samples


# 情感 → 音频参数 (mock backend)
EMOTION_AUDIO_MAP = {
    "neutral": {"freq": 220, "volume": 0.6},
    "happy":   {"freq": 330, "volume": 0.8},
    "sad":     {"freq": 180, "volume": 0.5},
    "excited": {"freq": 440, "volume": 0.9},
    "calm":    {"freq": 200, "volume": 0.4},
}

# Emotion → Alibaba Cloud NLS speech_rate adjustment
# Maps emotion to speed offset (-500 to 500)
EMOTION_SPEED_MAP = {
    "neutral": 0,
    "happy":   50,
    "sad":     -80,
    "excited": 100,
    "calm":    -40,
    "warm":    30,
    "angry":   80,
}


class TTSResult:
    """合成结果。"""
    def __init__(self, request_id: str, total_chunks: int, duration_ms: int):
        self.request_id = request_id
        self.total_chunks = total_chunks
        self.duration_ms = duration_ms


class TTSEngine:
    """Streaming TTS engine with dual backends.

    Parameters
    ----------
    sample_rate:
        Audio sample rate in Hz.
    chunk_size:
        PCM samples per chunk.
    cloud_config:
        CloudTTSConfig for Alibaba NLS backend. Required if using cloud mode.
    """

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        chunk_size: int = CHUNK_SIZE,
        cloud_config: CloudTTSConfig | None = None,
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.cloud_config = cloud_config
        self._phase = 0.0  # mock sine wave phase accumulator

    @property
    def backend(self) -> str:
        """Return the active backend name."""
        if self.cloud_config and self.cloud_config.access_key_id:
            return "cloud"
        return "mock"

    def synthesize_stream(
        self,
        request_id: str,
        features: LinguisticFeatures,
        emotion: EmotionTag,
        speed: float,
        on_chunk: Callable,
        on_complete: Callable,
        on_error: Callable,
        text: str = "",
    ):
        """流式合成。逐 chunk 回调。（兼容原接口）

        Dispatches to the correct backend based on config.
        """
        if self.backend == "cloud":
            self._synthesize_cloud(
                request_id, features, emotion, speed,
                on_chunk, on_complete, on_error, text=text,
            )
        else:
            self._synthesize_mock(
                request_id, features, emotion, speed,
                on_chunk, on_complete, on_error,
            )

    # ── Mock Backend (sine wave) ─────────────────────────────

    def _synthesize_mock(
        self,
        request_id: str,
        features: LinguisticFeatures,
        emotion: EmotionTag,
        speed: float,
        on_chunk: Callable,
        on_complete: Callable,
        on_error: Callable,
    ):
        """Mock: 正弦波生成。根据 emotion 调整频率和音量。"""
        logger.info("╔═══════════════════════════════════════════")
        logger.info(f"║ REQUEST: {request_id}  [MOCK BACKEND]")
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
            logger.error(f"TTS Engine [mock] error: {e}", exc_info=True)
            on_error(4001, f"TTS Engine mock inference failed: {e}")

    # ── Cloud Backend (Alibaba NLS) ──────────────────────────

    def _synthesize_cloud(
        self,
        request_id: str,
        features: LinguisticFeatures,
        emotion: EmotionTag,
        speed: float,
        on_chunk: Callable,
        on_complete: Callable,
        on_error: Callable,
        text: str = "",
    ):
        """Cloud: 阿里云 NLS 流式 TTS API。

        Runs the async WebSocket client in a dedicated event loop
        on the calling thread (which is *already* inside a thread
        pool executor managed by grpc_service.py).
        """
        if not self.cloud_config:
            on_error(6001, "Cloud TTS config not provided")
            return

        logger.info("╔═══════════════════════════════════════════")
        logger.info(f"║ REQUEST: {request_id}  [CLOUD BACKEND]")
        logger.info(f"║ VOICE: {self.cloud_config.voice}")
        logger.info(f"║ ENDPOINT: {self.cloud_config.endpoint}")

        # Use original Chinese text, not Bopomofo phonemes
        if not text:
            text = self._features_to_text(features)

        # Apply emotion-based speed adjustment
        emotion_speed_offset = EMOTION_SPEED_MAP.get(emotion.emotion, 0)
        base_speed = self.cloud_config.speech_rate + emotion_speed_offset
        # Scale by the user-requested speed factor (0.5 - 2.0)
        adjusted_speed = int(base_speed + (speed - 1.0) * 200)
        adjusted_speed = max(-500, min(500, adjusted_speed))

        # Create a modified config with adjusted speed
        config = CloudTTSConfig(
            access_key_id=self.cloud_config.access_key_id,
            access_key_secret=self.cloud_config.access_key_secret,
            app_key=self.cloud_config.app_key,
            endpoint=self.cloud_config.endpoint,
            voice=self.cloud_config.voice,
            sample_rate=self.sample_rate,
            speech_rate=adjusted_speed,
            volume=self.cloud_config.volume,
        )

        # Bridge async → sync via temporary event loop on this thread
        def _run_cloud_loop() -> None:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._async_synthesize(
                    config, text, request_id, on_chunk, on_complete, on_error,
                ))
            finally:
                loop.close()

        _run_cloud_loop()

    async def _async_synthesize(
        self,
        config: CloudTTSConfig,
        text: str,
        request_id: str,
        on_chunk: Callable,
        on_complete: Callable,
        on_error: Callable,
    ) -> None:
        """Async synthesis coroutine. Connects to NLS, streams audio."""
        client = CloudTTSClient(config)
        try:
            await client.connect()

            # Wrap completion to convert CloudTTSResult → TTSResult
            def _on_complete(result: CloudTTSResult) -> None:
                on_complete(TTSResult(
                    result.request_id,
                    result.total_chunks,
                    result.duration_ms,
                ))

            await client.synthesize(
                text=text,
                on_chunk=on_chunk,
                on_complete=_on_complete,
                on_error=on_error,
                request_id=request_id,
            )

        except ConnectionError as e:
            logger.error("nls.connect_failed", request_id=request_id, error=str(e))
            on_error(6001, f"Failed to connect to NLS gateway: {e}")
        except Exception as e:
            logger.exception("cloud_tts.error", request_id=request_id)
            on_error(6005, f"Cloud TTS error: {e}")
        finally:
            await client.disconnect()

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _features_to_text(features: LinguisticFeatures) -> str:
        """Reconstruct a plain-text representation from linguistic features.

        The cloud TTS API takes natural language text — we pass the phonetic
        representation as a fallback, or better, let the caller provide text.

        NOTE: The grpc_service._run_synthesis_pipeline already has the original
        ``text`` before linguistic processing. We should use that instead.
        This method exists as a safety net for callers that only have features.
        """
        # Phonemes are Bopomofo symbols — join them
        if features.phonemes:
            return "".join(features.phonemes)
        return ""
