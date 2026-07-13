"""
M1 — TTS Streaming Gateway
POC: FastAPI WebSocket + gRPC server + REST voice management.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Optional

import grpc
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

from . import tts_pb2, tts_pb2_grpc

logger = logging.getLogger(__name__)


class TTSGateway:
    """
    TTS Streaming Gateway.
    - WebSocket: /ws/v1/tts (双向 JSON 帧)
    - gRPC: BidirectionalSynthesize + Health
    - REST: /api/v1/voices/* (音色管理)
    """

    def __init__(self, session_mgr, pipeline_runner):
        self.sm = session_mgr
        self.run_pipeline = pipeline_runner  # async func(request_id, text, voice_id, emotion, speed) → stream
        self._start_time = time.time()

    # ============================================================
    # REST Router (音色管理 + Health)
    # ============================================================
    def build_router(self, speaker_mgr) -> APIRouter:
        """构建所有 REST 路由（含 health + voices），统一 /api/v1 前缀。"""
        router = APIRouter(prefix="/api/v1")

        @router.get("/health")
        async def health():
            return {
                "status": "healthy",
                "version": "1.0.0-poc",
                "uptime_seconds": int(time.time() - self._start_time),
            }

        @router.get("/voices")
        async def list_voices():
            return {"voices": speaker_mgr.list_voices(), "total": len(speaker_mgr.list_voices())}

        @router.get("/voices/{voice_id}")
        async def get_voice(voice_id: str):
            v = speaker_mgr.get_voice_by_id(voice_id)
            if not v:
                raise HTTPException(status_code=404, detail={"error_code": 3001, "message": "voice_id not found"})
            return v

        @router.post("/voices")
        async def create_voice(data: dict):
            from .speaker_manager import VoiceProfile
            voice_id = data.get("voice_id") or f"voice-{uuid.uuid4().hex[:8]}"
            vp = VoiceProfile(voice_id=voice_id, **{k: v for k, v in data.items() if k != "voice_id"})
            speaker_mgr.create_voice(vp)
            return {"voice_id": voice_id, "status": "created"}

        @router.delete("/voices/{voice_id}")
        async def delete_voice(voice_id: str):
            ok = speaker_mgr.delete_voice(voice_id)
            if not ok:
                raise HTTPException(status_code=404, detail={"error_code": 3001, "message": "voice_id not found"})
            return {"voice_id": voice_id, "status": "deleted"}

        return router

    # ============================================================
    # WebSocket Handler
    # ============================================================
    async def handle_websocket(self, ws: WebSocket):
        """WebSocket 主循环。"""
        await ws.accept()
        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        self.sm.create_session(session_id)
        logger.info(f"WS session created: {session_id}")

        try:
            while True:
                raw = await ws.receive_text()
                if not raw.strip():
                    continue
                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    await ws.send_text(json.dumps(
                        {"type": "error", "error_code": 1000, "message": "invalid JSON"}))
                    continue

                frame_type = frame.get("type", "")

                if frame_type == "synthesis_request":
                    await self._handle_synthesis_request(ws, session_id, frame)

                elif frame_type == "cancel":
                    # 取消 — 当前不做复杂处理，POC 简单忽略后续 chunk
                    logger.info(f"Cancel request: {frame.get('request_id')}")

                elif frame_type == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))

                else:
                    await ws.send_text(json.dumps(
                        {"type": "error", "error_code": 1001, "message": f"unknown frame type: {frame_type}"}))

        except WebSocketDisconnect:
            logger.info(f"WS disconnected: {session_id}")
        except Exception as e:
            logger.error(f"WS error [{session_id}]: {e}")
        finally:
            self.sm.destroy_session(session_id)

    async def _handle_synthesis_request(self, ws: WebSocket, session_id: str, frame: dict):
        """处理一次合成请求：全管线 + 流式推送。"""
        request_id = frame.get("request_id", uuid.uuid4().hex[:8])
        text = frame.get("text", "")
        voice_id = frame.get("voice_id", "default")
        emotion = frame.get("emotion", "neutral")
        speed = float(frame.get("speed", 1.0))

        if not text:
            await ws.send_text(json.dumps(
                {"type": "error", "request_id": request_id, "error_code": 2002, "message": "text is empty"}))
            return

        # 更新会话状态
        self.sm.update_session(session_id, voice_id=voice_id, emotion=emotion, speed=speed)

        # 流式执行全管线
        async for msg in self.run_pipeline(request_id, text, voice_id, emotion, speed):
            await ws.send_text(json.dumps(msg))

    # ============================================================
    # gRPC Servicer
    # ============================================================
    class _GrpcServicer(tts_pb2_grpc.TTSServicer):
        def __init__(self, gateway: "TTSGateway"):
            self.gw = gateway

        async def BidirectionalSynthesize(self, request_iterator, context):
            """gRPC 双向流。"""
            session_id = f"grpc-{uuid.uuid4().hex[:12]}"
            self.gw.sm.create_session(session_id)

            try:
                async for client_msg in request_iterator:
                    which = client_msg.WhichOneof("payload")

                    if which == "synthesis_request":
                        req = client_msg.synthesis_request
                        request_id = req.request_id or uuid.uuid4().hex[:8]
                        # 流式执行全管线
                        async for server_msg in self.gw.run_pipeline(
                            request_id, req.text, req.voice_id, req.emotion, req.speed
                        ):
                            yield self._to_grpc_message(server_msg)

                    elif which == "cancel":
                        logger.info(f"gRPC cancel: {client_msg.cancel.request_id}")

                    elif which == "ping":
                        reply = tts_pb2.ServerMessage()
                        reply.pong.SetInParent()
                        yield reply

            finally:
                self.gw.sm.destroy_session(session_id)

        async def Health(self, request, context):
            reply = tts_pb2.HealthResponse()
            reply.status = "healthy"
            reply.version = "1.0.0-poc"
            reply.uptime_seconds = int(time.time() - self.gw._start_time)
            return reply

        @staticmethod
        def _to_grpc_message(msg: dict) -> tts_pb2.ServerMessage:
            """将 Python dict 帧转为 gRPC ServerMessage。"""
            reply = tts_pb2.ServerMessage()
            t = msg.get("type", "")
            if t == "audio_chunk":
                chunk = tts_pb2.AudioChunk()
                chunk.request_id = msg.get("request_id", "")
                chunk.sequence = msg.get("sequence", 0)
                import base64
                chunk.pcm_data = base64.b64decode(msg.get("data", ""))
                chunk.sample_rate = msg.get("sample_rate", 16000)
                reply.audio_chunk.CopyFrom(chunk)
            elif t == "synthesis_complete":
                sc = tts_pb2.SynthesisComplete()
                sc.request_id = msg.get("request_id", "")
                sc.total_chunks = msg.get("total_chunks", 0)
                sc.duration_ms = msg.get("duration_ms", 0)
                reply.synthesis_complete.CopyFrom(sc)
            elif t == "error":
                err = tts_pb2.ErrorMessage()
                err.request_id = msg.get("request_id", "")
                err.error_code = msg.get("error_code", 0)
                err.message = msg.get("message", "")
                reply.error.CopyFrom(err)
            else:
                reply.pong.SetInParent()
            return reply

    def grpc_servicer(self):
        return self._GrpcServicer(self)
