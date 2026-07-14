"""
TTS HTTP Server — FastAPI REST + WebSocket.

Provides:
  - GET    /api/v1/health              — Health check
  - GET    /api/v1/voices              — List voices
  - POST   /api/v1/voices              — Create voice
  - GET    /api/v1/voices/{voice_id}   — Get voice
  - DELETE /api/v1/voices/{voice_id}   — Delete voice
  - POST   /api/v1/synthesize          — Non-streaming synthesis
  - WS     /ws/v1/tts                  — Streaming synthesis via WebSocket
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Monorepo path setup
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
TTS_SVC_ROOT = REPO_ROOT / "services" / "tts-svc"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TTS_SVC_ROOT))

from libs.common.logging import get_logger

# proto
from libs.proto.tts.v1 import tts_pb2
from libs.proto.common.v1 import common_pb2

logger = get_logger(__name__)


# ── Request / Response models ──

class SynthesizeRequest(BaseModel):
    text: str
    voice_id: str = "default"
    emotion: str = "neutral"
    speed: float = 1.0
    request_id: str = ""


class CreateVoiceRequest(BaseModel):
    name: str = ""
    gender: int = 1  # GENDER_FEMALE
    age_range: str = "25-35"
    language: str = "zh-CN"
    style: int = 1  # VOICE_STYLE_PASSIONATE
    description: str = ""


EMOTION_STR_TO_PROTO = {
    "neutral": tts_pb2.EMOTION_NEUTRAL,
    "happy": tts_pb2.EMOTION_HAPPY,
    "excited": tts_pb2.EMOTION_EXCITED,
    "sad": tts_pb2.EMOTION_SAD,
    "calm": tts_pb2.EMOTION_UNSPECIFIED,
    "warm": tts_pb2.EMOTION_WARM,
    "angry": tts_pb2.EMOTION_ANGRY,
}

EMOTION_PROTO_TO_STR: dict[int, str] = {
    tts_pb2.EMOTION_UNSPECIFIED: "neutral",
    tts_pb2.EMOTION_NEUTRAL: "neutral",
    tts_pb2.EMOTION_HAPPY: "happy",
    tts_pb2.EMOTION_EXCITED: "excited",
    tts_pb2.EMOTION_WARM: "warm",
    tts_pb2.EMOTION_SAD: "sad",
    tts_pb2.EMOTION_ANGRY: "angry",
}


def create_http_app(
    grpc_service: Any,
    voice_store: Any,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        grpc_service: An instance of ``TTSGrpcService`` (duck-typed).
        voice_store: An instance of ``VoiceStore`` (duck-typed).
    """
    app = FastAPI(
        title="TTS Service",
        version="0.2.0",
        description="Digital Human Livestream Shopping TTS Engine",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _start_time = time.time()

    # ── Health ──

    @app.get("/api/v1/health")
    async def health():
        return {
            "status": "healthy",
            "version": "0.2.0",
            "uptime_seconds": int(time.time() - _start_time),
        }

    # ── Voice CRUD ──

    @app.get("/api/v1/voices")
    async def list_voices():
        voices = voice_store.list()
        return {
            "voices": [_voice_to_dict(v) for v in voices],
            "total": len(voices),
        }

    @app.get("/api/v1/voices/{voice_id}")
    async def get_voice(voice_id: str):
        voice = voice_store.get(voice_id)
        if not voice:
            raise HTTPException(
                status_code=404,
                detail={"error_code": 3007, "message": f"voice_id '{voice_id}' not found"},
            )
        return _voice_to_dict(voice)

    @app.post("/api/v1/voices")
    async def create_voice(data: CreateVoiceRequest):
        voice_id = f"voice-{uuid.uuid4().hex[:8]}"
        proto_voice = tts_pb2.Voice(
            voice_id=voice_id,
            name=data.name or f"Voice {voice_id}",
            gender=data.gender,
            age_range=data.age_range,
            language=data.language,
            style=data.style,
            description=data.description,
            status=tts_pb2.VOICE_STATUS_ACTIVE,
        )
        created = voice_store.create(proto_voice)
        return _voice_to_dict(created)

    @app.delete("/api/v1/voices/{voice_id}")
    async def delete_voice(voice_id: str):
        ok = voice_store.delete(voice_id)
        if not ok:
            raise HTTPException(
                status_code=404,
                detail={"error_code": 3007, "message": f"voice_id '{voice_id}' not found or protected"},
            )
        return {"voice_id": voice_id, "status": "deleted"}

    # ── Non-streaming Synthesis ──

    @app.post("/api/v1/synthesize")
    async def synthesize(data: SynthesizeRequest):
        """Non-streaming synthesis. Returns the full PCM audio."""
        request_id = data.request_id or f"syn-{uuid.uuid4().hex[:12]}"
        emotion = EMOTION_STR_TO_PROTO.get(data.emotion, tts_pb2.EMOTION_NEUTRAL)

        # Build a SynthesisRequest proto and call the gRPC service directly
        proto_req = tts_pb2.SynthesisRequest(
            request_id=request_id,
            text=data.text,
            voice_id=data.voice_id,
            emotion=emotion,
            speed=data.speed,
            enable_cache=True,
        )

        # We need a dummy context - use the service's synthesize method
        # Since we can't easily create a gRPC context, collect chunks directly
        from src.grpc_service import synthesize_async

        emotion_str = EMOTION_PROTO_TO_STR.get(emotion, "neutral")
        all_audio = bytearray()
        result_info: dict[str, Any] = {}

        async for msg in synthesize_async(
            request_id, data.text, data.voice_id, emotion_str, data.speed,
        ):
            if msg["type"] == "audio_chunk":
                all_audio.extend(msg["data"])
            elif msg["type"] == "synthesis_complete":
                result_info = {
                    "total_chunks": msg["total_chunks"],
                    "duration_ms": msg["duration_ms"],
                    "sample_rate": msg.get("sample_rate", 16000),
                    "cache_hit": msg.get("cache_hit", False),
                }
            elif msg["type"] == "error":
                raise HTTPException(
                    status_code=500,
                    detail=msg,
                )

        import base64
        return {
            "request_id": request_id,
            "audio_base64": base64.b64encode(bytes(all_audio)).decode(),
            "sample_rate": result_info.get("sample_rate", 16000),
            "duration_ms": result_info.get("duration_ms", 0),
            "total_chunks": result_info.get("total_chunks", 0),
        }

    # ── Streaming WebSocket ──

    @app.websocket("/ws/v1/tts")
    async def websocket_tts(ws: WebSocket):
        """WebSocket streaming endpoint for TTS.

        Protocol:
        Client sends JSON frames:
            {"type": "synthesis_request", "request_id": "...", "text": "...",
             "voice_id": "...", "emotion": "...", "speed": 1.0}

        Server sends JSON frames:
            {"type": "audio_chunk", "sequence": N, "data": "<base64>"}
            {"type": "synthesis_complete", ...}
            {"type": "error", ...}
            {"type": "pong"}  (in response to {"type": "ping"})
        """
        await ws.accept()
        session_id = f"ws-{uuid.uuid4().hex[:12]}"
        logger.info("ws.connected", session_id=session_id)

        try:
            while True:
                raw = await ws.receive_text()
                if not raw.strip():
                    continue

                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    await ws.send_text(json.dumps(
                        {"type": "error", "error_code": 1000, "message": "invalid JSON"},
                    ))
                    continue

                frame_type = frame.get("type", "")

                if frame_type == "synthesis_request":
                    await _handle_ws_synthesis(ws, frame, session_id)

                elif frame_type == "cancel":
                    logger.info("ws.cancel", session_id=session_id, request_id=frame.get("request_id"))

                elif frame_type == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))

                else:
                    await ws.send_text(json.dumps(
                        {"type": "error", "error_code": 1001,
                         "message": f"unknown frame type: {frame_type}"},
                    ))

        except WebSocketDisconnect:
            logger.info("ws.disconnected", session_id=session_id)
        except Exception as exc:
            logger.error("ws.error", session_id=session_id, error=str(exc))
        finally:
            logger.info("ws.closed", session_id=session_id)

    return app


# ── Internal helpers ──

async def _handle_ws_synthesis(ws: WebSocket, frame: dict, session_id: str) -> None:
    """Handle a WebSocket synthesis request."""
    request_id = frame.get("request_id", uuid.uuid4().hex[:8])
    text = frame.get("text", "")
    voice_id = frame.get("voice_id", "default")
    emotion_str = frame.get("emotion", "neutral")
    speed = float(frame.get("speed", 1.0))

    if not text:
        await ws.send_text(json.dumps(
            {"type": "error", "request_id": request_id,
             "error_code": 2002, "message": "text is empty"},
        ))
        return

    from src.grpc_service import synthesize_async

    async for msg in synthesize_async(request_id, text, voice_id, emotion_str, speed):
        msg_type = msg.get("type")

        if msg_type == "audio_chunk":
            import base64
            await ws.send_text(json.dumps({
                "type": "audio_chunk",
                "request_id": msg["request_id"],
                "sequence": msg["sequence"],
                "data": base64.b64encode(msg["data"]).decode(),
                "sample_rate": msg.get("sample_rate", 16000),
            }))

        elif msg_type == "synthesis_complete":
            await ws.send_text(json.dumps({
                "type": "synthesis_complete",
                "request_id": msg["request_id"],
                "total_chunks": msg["total_chunks"],
                "duration_ms": msg["duration_ms"],
                "sample_rate": msg.get("sample_rate", 16000),
            }))

        elif msg_type == "error":
            await ws.send_text(json.dumps({
                "type": "error",
                "request_id": msg["request_id"],
                "error_code": msg["error_code"],
                "message": msg["message"],
            }))


def _voice_to_dict(voice: tts_pb2.Voice) -> dict[str, Any]:
    """Convert a proto Voice to a plain dict for JSON serialization."""
    from google.protobuf.json_format import MessageToDict
    return MessageToDict(
        voice,
        preserving_proto_field_name=True,
        always_print_fields_with_no_presence=True,
        use_integers_for_enums=False,
    )


# ── Direct run (dev) ──

if __name__ == "__main__":
    import uvicorn
    from src.grpc_service import TTSGrpcService, VoiceStore

    store = VoiceStore()
    svc = TTSGrpcService(voice_store=store)
    app = create_http_app(svc, store)
    uvicorn.run(app, host="0.0.0.0", port=8080)
