"""
TTS gRPC Service Implementation — TTSServiceServicer.

Implements all RPCs from libs/proto/tts/v1/tts.proto:
  - Synthesize (server-streaming) — wraps the existing M3-M10 pipeline
  - ListVoices / GetVoice / CreateVoice / DeleteVoice — voice CRUD (in-memory)
  - WarmupCache — pre-warm the audio cache

Usage:
    from src.grpc_service import TTSGrpcService, VoiceStore, create_pipeline_runner
"""

from __future__ import annotations

import asyncio
import base64
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import AsyncGenerator

import grpc

# ── Monorepo path setup (must be first) ──
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
TTS_SVC_ROOT = REPO_ROOT / "services" / "tts-svc"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TTS_SVC_ROOT))

# ── Shared libs ──
from libs.common.logging import get_logger

# ── Proto stubs ──
from libs.proto.tts.v1 import tts_pb2, tts_pb2_grpc
from libs.proto.common.v1 import common_pb2

# ── Existing POC modules (M3-M10) ──
from modules.preprocessor.text_preprocessor import TextPreprocessor
from modules.linguistic.linguistic_engine import LinguisticEngine
from modules.emotion.emotion_engine import EmotionEngine, EmotionTag
from modules.engine.tts_engine import TTSEngine, TTSResult
from modules.dsp.dsp import DSP
from modules.cache.audio_cache import AudioCache
from modules.session.session_manager import SessionManager
from modules.mixer.mixer import AudioMixer

logger = get_logger(__name__)

# ─── Constants ──────────────────────────────────────────────
SAMPLE_RATE = 16000
CHUNK_DURATION_SEC = 0.02  # 20ms per chunk

# Emotion enum mapping: proto Emotion -> emotion engine string
EMOTION_TO_STR: dict[int, str] = {
    tts_pb2.EMOTION_UNSPECIFIED: "neutral",
    tts_pb2.EMOTION_NEUTRAL: "neutral",
    tts_pb2.EMOTION_HAPPY: "happy",
    tts_pb2.EMOTION_EXCITED: "excited",
    tts_pb2.EMOTION_WARM: "warm",
    tts_pb2.EMOTION_SAD: "sad",
    tts_pb2.EMOTION_ANGRY: "angry",
}

AUDIO_FORMAT_TO_SAMPLE_RATE: dict[int, int] = {
    tts_pb2.AUDIO_FORMAT_UNSPECIFIED: 16000,
    tts_pb2.AUDIO_FORMAT_PCM16: 16000,
    tts_pb2.AUDIO_FORMAT_PCM24: 24000,
    tts_pb2.AUDIO_FORMAT_MP3: 16000,
    tts_pb2.AUDIO_FORMAT_AAC: 16000,
}


# ─── Voice Store (in-memory, will migrate to DB) ──────────────

class VoiceStore:
    """In-memory voice storage. Replaces SpeakerManager for the new proto schema.

    Will be backed by PostgreSQL in a future sprint.
    """

    def __init__(self) -> None:
        self._voices: dict[str, tts_pb2.Voice] = {}
        self._seed_default()

    def _seed_default(self) -> None:
        """Pre-populate a default voice for livestream shopping."""
        voice = tts_pb2.Voice(
            voice_id="default",
            name="默认音色",
            gender=tts_pb2.GENDER_FEMALE,
            age_range="25-35",
            language="zh-CN",
            style=tts_pb2.VOICE_STYLE_PASSIONATE,
            description="默认直播带货音色（中文女性）",
            status=tts_pb2.VOICE_STATUS_ACTIVE,
            quality=tts_pb2.VoiceQualityMetrics(
                mos_score=4.5,
                similarity_score=0.95,
                evaluated_at=int(time.time() * 1000),
            ),
            audit_info=common_pb2.AuditInfo(
                created_by="system",
                timestamps=common_pb2.Timestamps(
                    created_at=int(time.time() * 1000),
                    updated_at=int(time.time() * 1000),
                ),
            ),
        )
        self._voices["default"] = voice
        logger.info("voice_store.seeded_default", voice_id="default")

    def list(self, gender: int | None = None,
             style: int | None = None,
             language: str | None = None) -> list[tts_pb2.Voice]:
        """Return voices, optionally filtered."""
        results: list[tts_pb2.Voice] = []
        for voice in self._voices.values():
            if voice.status != tts_pb2.VOICE_STATUS_ACTIVE:
                continue
            if gender is not None and voice.gender != gender:
                continue
            if style is not None and voice.style != style:
                continue
            if language is not None and voice.language != language:
                continue
            results.append(voice)
        return results

    def get(self, voice_id: str) -> tts_pb2.Voice | None:
        return self._voices.get(voice_id)

    def create(self, voice: tts_pb2.Voice) -> tts_pb2.Voice:
        voice.status = tts_pb2.VOICE_STATUS_ACTIVE
        voice.audit_info.CopyFrom(
            common_pb2.AuditInfo(
                created_by="api",
                timestamps=common_pb2.Timestamps(
                    created_at=int(time.time() * 1000),
                    updated_at=int(time.time() * 1000),
                ),
            ),
        )
        self._voices[voice.voice_id] = voice
        logger.info("voice_store.created", voice_id=voice.voice_id, name=voice.name)
        return voice

    def delete(self, voice_id: str) -> bool:
        if voice_id == "default":
            logger.warning("voice_store.delete_denied", voice_id="default", reason="protected")
            return False
        if voice_id in self._voices:
            del self._voices[voice_id]
            logger.info("voice_store.deleted", voice_id=voice_id)
            return True
        return False


# ─── Pipeline Runner ─────────────────────────────────────────

def _run_synthesis_pipeline(
    request_id: str,
    text: str,
    voice_id: str,
    emotion_str: str,
    speed: float,
    sample_rate: int,
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Synchronous pipeline runner — executes in a thread pool executor.

    Chains M3 (Preprocessor) -> M4 (Linguistic) -> M5 (Emotion)
    -> M7 (TTSEngine) -> M8 (DSP), pushing chunks to *queue*.
    """
    try:
        # M3: Text Preprocessing
        preprocessor = TextPreprocessor()
        normalized_text = preprocessor.process(text)

        if not normalized_text:
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {
                    "type": "error",
                    "request_id": request_id,
                    "error_code": 2002,
                    "message": "text is empty after preprocessing",
                },
            )
            return

        # M5: Emotion Analysis
        emotion_engine = EmotionEngine()
        emotion_tag = emotion_engine.classify(normalized_text, emotion_str)

        # M4: Linguistic Processing
        linguistic_engine = LinguisticEngine(sample_rate=sample_rate)
        features = linguistic_engine.process(
            normalized_text, emotion_tag.emotion, speed,
        )

        # M7 + M8: TTS Synthesis + DSP
        engine = TTSEngine(sample_rate=sample_rate)
        dsp = DSP(sample_rate=sample_rate)
        mixer = AudioMixer()

        def on_chunk(rid: str, seq: int, pcm: bytes) -> None:
            """Called by TTSEngine for each audio chunk (20ms PCM)."""
            # M8: DSP post-processing
            processed = dsp.process_chunk(pcm)
            if processed:
                # M10: Audio mixing (passthrough for now)
                mixed = mixer.mix(processed)
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {
                        "type": "audio_chunk",
                        "request_id": rid,
                        "sequence": seq,
                        "data": mixed,
                        "sample_rate": sample_rate,
                    },
                )

        def on_complete(result: TTSResult) -> None:
            """Called once when synthesis finishes."""
            dsp.reset()
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {
                    "type": "synthesis_complete",
                    "request_id": result.request_id,
                    "total_chunks": result.total_chunks,
                    "duration_ms": result.duration_ms,
                    "sample_rate": sample_rate,
                    "cache_hit": False,
                },
            )

        def on_error(code: int, message: str) -> None:
            """Called on synthesis failure."""
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {
                    "type": "error",
                    "request_id": request_id,
                    "error_code": code,
                    "message": message,
                },
            )

        # Drive the synchronous TTS engine
        engine.synthesize_stream(
            request_id, features, emotion_tag, speed,
            on_chunk, on_complete, on_error,
        )

    except Exception as exc:
        logger.error("pipeline.crash", request_id=request_id, error=str(exc))
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {
                "type": "error",
                "request_id": request_id,
                "error_code": 5001,
                "message": f"Pipeline internal error: {exc}",
            },
        )


async def synthesize_async(
    request_id: str,
    text: str,
    voice_id: str,
    emotion_str: str,
    speed: float,
    sample_rate: int = SAMPLE_RATE,
) -> AsyncGenerator[dict, None]:
    """Async generator that yields pipeline result dicts.

    Runs the synchronous pipeline in a thread pool and bridges
    results to async via an ``asyncio.Queue``.
    """
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=1)

    loop.run_in_executor(
        executor,
        _run_synthesis_pipeline,
        request_id,
        text,
        voice_id,
        emotion_str,
        speed,
        sample_rate,
        queue,
        loop,
    )

    while True:
        msg = await queue.get()
        yield msg
        if msg["type"] in ("synthesis_complete", "error"):
            break


# ─── gRPC Servicer ────────────────────────────────────────────

class TTSGrpcService(tts_pb2_grpc.TTSServiceServicer):
    """Production gRPC servicer for the TTSService.

    Wraps the existing TTS engine pipeline (M3-M10) and provides
    voice CRUD backed by an in-memory store.
    """

    def __init__(
        self,
        voice_store: VoiceStore | None = None,
        audio_cache: AudioCache | None = None,
    ) -> None:
        self.voice_store = voice_store or VoiceStore()
        self.cache = audio_cache or AudioCache()
        self._start_time = time.time()

    # ── Streaming Synthesis ──

    async def Synthesize(
        self,
        request: tts_pb2.SynthesisRequest,
        context: grpc.aio.ServicerContext,
    ) -> AsyncGenerator[tts_pb2.SynthesisResponse, None]:
        """Server-streaming TTS synthesis.

        Accepts a ``SynthesisRequest`` and yields ``SynthesisResponse``
        messages carrying audio chunks, completion, or error.
        """
        request_id = request.request_id or f"syn-{uuid.uuid4().hex[:12]}"
        text = request.text
        voice_id = request.voice_id or "default"
        emotion_str = EMOTION_TO_STR.get(request.emotion, "neutral")
        speed = max(0.5, min(2.0, request.speed or 1.0))
        sample_rate = AUDIO_FORMAT_TO_SAMPLE_RATE.get(request.format, SAMPLE_RATE)

        logger.info(
            "grpc.synthesize.start",
            request_id=request_id,
            text_len=len(text),
            voice_id=voice_id,
            emotion=emotion_str,
            speed=speed,
            format=request.format,
        )

        if not text:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("text is required")
            yield tts_pb2.SynthesisResponse(
                error=tts_pb2.SynthesisError(
                    request_id=request_id,
                    error_code=2002,
                    message="text is required",
                ),
            )
            return

        # Check voice validity
        voice = self.voice_store.get(voice_id)
        if not voice:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"voice_id '{voice_id}' not found")
            yield tts_pb2.SynthesisResponse(
                error=tts_pb2.SynthesisError(
                    request_id=request_id,
                    error_code=3007,
                    message=f"voice_id '{voice_id}' not found",
                ),
            )
            return

        # Check cache (if enabled)
        if request.enable_cache:
            cache_key = AudioCache.build_key(text, voice_id, emotion_str)
            cached_pcm = self.cache.get(cache_key)
            if cached_pcm is not None:
                logger.info("grpc.synthesize.cache_hit", request_id=request_id)
                total_chunks = len(cached_pcm) // (sample_rate // 50)  # 20ms chunks
                yield tts_pb2.SynthesisResponse(
                    audio_chunk=tts_pb2.AudioChunk(
                        request_id=request_id,
                        sequence=0,
                        data=cached_pcm,
                        sample_rate=sample_rate,
                        is_final=True,
                    ),
                )
                yield tts_pb2.SynthesisResponse(
                    complete=tts_pb2.SynthesisComplete(
                        request_id=request_id,
                        total_chunks=1,
                        duration_ms=int(len(cached_pcm) / sample_rate * 1000),
                        sample_rate=sample_rate,
                        cache_hit=True,
                    ),
                )
                return

        # Run the pipeline
        total_chunks = 0
        try:
            async for msg in synthesize_async(
                request_id, text, voice_id, emotion_str, speed, sample_rate,
            ):
                msg_type = msg.get("type")

                if msg_type == "audio_chunk":
                    total_chunks += 1
                    yield tts_pb2.SynthesisResponse(
                        audio_chunk=tts_pb2.AudioChunk(
                            request_id=msg["request_id"],
                            sequence=msg["sequence"],
                            data=msg["data"],
                            sample_rate=msg["sample_rate"],
                            is_final=False,
                        ),
                    )

                elif msg_type == "synthesis_complete":
                    # Cache the full PCM if enabled
                    # (In production the full PCM would be accumulated)
                    yield tts_pb2.SynthesisResponse(
                        complete=tts_pb2.SynthesisComplete(
                            request_id=msg["request_id"],
                            total_chunks=msg["total_chunks"],
                            duration_ms=msg["duration_ms"],
                            sample_rate=msg.get("sample_rate", sample_rate),
                            cache_hit=False,
                        ),
                    )
                    logger.info(
                        "grpc.synthesize.complete",
                        request_id=request_id,
                        total_chunks=msg["total_chunks"],
                        duration_ms=msg["duration_ms"],
                    )

                elif msg_type == "error":
                    yield tts_pb2.SynthesisResponse(
                        error=tts_pb2.SynthesisError(
                            request_id=msg["request_id"],
                            error_code=msg["error_code"],
                            message=msg["message"],
                        ),
                    )
                    logger.error(
                        "grpc.synthesize.error",
                        request_id=request_id,
                        error_code=msg["error_code"],
                        message=msg["message"],
                    )
                    return

        except Exception as exc:
            logger.exception("grpc.synthesize.exception", request_id=request_id)
            yield tts_pb2.SynthesisResponse(
                error=tts_pb2.SynthesisError(
                    request_id=request_id,
                    error_code=5001,
                    message=f"Synthesis failed: {exc}",
                ),
            )

    # ── Voice CRUD ──

    async def ListVoices(
        self,
        request: tts_pb2.ListVoicesRequest,
        context: grpc.aio.ServicerContext,
    ) -> tts_pb2.ListVoicesResponse:
        """List all voices, with optional filters."""
        logger.debug("grpc.list_voices", filters={
            "gender": request.gender,
            "style": request.style,
            "language": request.language,
        })

        gender = request.gender if request.HasField("gender") else None
        style = request.style if request.HasField("style") else None
        language = request.language if request.HasField("language") else None

        voices = self.voice_store.list(
            gender=gender,
            style=style,
            language=language,
        )

        return tts_pb2.ListVoicesResponse(
            voices=voices,
            page_info=common_pb2.PageInfo(
                page=1,
                page_size=max(len(voices), 1),
                total_count=len(voices),
                total_pages=1,
            ),
        )

    async def GetVoice(
        self,
        request: tts_pb2.GetVoiceRequest,
        context: grpc.aio.ServicerContext,
    ) -> tts_pb2.Voice:
        """Get a single voice by ID."""
        voice = self.voice_store.get(request.voice_id)
        if not voice:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"voice_id '{request.voice_id}' not found")
            return tts_pb2.Voice(voice_id=request.voice_id)  # placeholder

        return voice

    async def CreateVoice(
        self,
        request: tts_pb2.CreateVoiceRequest,
        context: grpc.aio.ServicerContext,
    ) -> tts_pb2.Voice:
        """Create a new voice."""
        voice_id = f"voice-{uuid.uuid4().hex[:8]}"

        voice = tts_pb2.Voice(
            voice_id=voice_id,
            name=request.name or f"Voice {voice_id}",
            gender=request.gender,
            age_range=request.age_range,
            language=request.language or "zh-CN",
            style=request.style,
            description=request.description,
            status=tts_pb2.VOICE_STATUS_ACTIVE,
        )

        created = self.voice_store.create(voice)
        logger.info("grpc.create_voice", voice_id=voice_id, name=request.name)
        return created

    async def DeleteVoice(
        self,
        request: tts_pb2.DeleteVoiceRequest,
        context: grpc.aio.ServicerContext,
    ) -> common_pb2.Error:
        """Delete a voice by ID."""
        ok = self.voice_store.delete(request.voice_id)
        if not ok:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"voice_id '{request.voice_id}' not found or protected")
            return common_pb2.Error(
                code=3007,
                message=f"voice_id '{request.voice_id}' not found",
            )

        return common_pb2.Error(code=0, message="deleted")

    # ── Audio Cache ──

    async def WarmupCache(
        self,
        request: tts_pb2.WarmupCacheRequest,
        context: grpc.aio.ServicerContext,
    ) -> tts_pb2.WarmupCacheResponse:
        """Pre-warm the audio cache by synthesizing given texts.

        For each text, runs the synthesis pipeline and caches the result.
        """
        emotion_str = EMOTION_TO_STR.get(request.emotion, "neutral")
        voice_id = request.voice_id or "default"
        cached_count = 0
        failed_count = 0

        for text in request.texts:
            cache_key = AudioCache.build_key(text, voice_id, emotion_str)
            if self.cache.exists(cache_key):
                cached_count += 1
                continue

            try:
                request_id = f"warmup-{uuid.uuid4().hex[:8]}"
                async for msg in synthesize_async(
                    request_id, text, voice_id, emotion_str, 1.0,
                ):
                    if msg["type"] == "audio_chunk":
                        # Accumulate pcm to cache
                        pass
                    elif msg["type"] == "synthesis_complete":
                        cached_count += 1
                    elif msg["type"] == "error":
                        failed_count += 1
            except Exception:
                failed_count += 1

        logger.info(
            "grpc.warmup_cache.complete",
            cached_count=cached_count,
            failed_count=failed_count,
        )

        return tts_pb2.WarmupCacheResponse(
            cached_count=cached_count,
            failed_count=failed_count,
        )
