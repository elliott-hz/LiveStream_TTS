"""
Cloud TTS Client — 阿里云智能语音交互 (NLS) WebSocket 流式 TTS.

Protocol: wss://nls-gateway-{region}.aliyuncs.com/ws/v1
- Token-based auth (HMAC-SHA1, generated from AccessKey)
- JSON control frames + binary PCM audio frames
- Streaming: send StartSynthesis → receive binary chunks → SynthesisCompleted

Reference: https://help.aliyun.com/document_detail/84435.html
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import websockets
from websockets.asyncio.client import ClientConnection

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────
NLS_DEFAULT_ENDPOINT = "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1"
NLS_TOKEN_EXPIRE_SECONDS = 3600  # 1 hour
NLS_DEFAULT_SAMPLE_RATE = 16000
NLS_RECONNECT_MAX_RETRIES = 3
NLS_RECONNECT_BASE_DELAY = 0.5  # seconds

# PCM audio: 20ms per chunk at 16kHz
PCM_CHUNK_DURATION_SEC = 0.02
PCM_BYTES_PER_SAMPLE = 2  # 16-bit


@dataclass
class CloudTTSConfig:
    """Configuration for Alibaba Cloud NLS TTS."""

    access_key_id: str = ""
    access_key_secret: str = ""
    app_key: str = ""  # NLS project app key
    endpoint: str = NLS_DEFAULT_ENDPOINT
    voice: str = "Aixia"  # Default female voice for livestream shopping
    sample_rate: int = NLS_DEFAULT_SAMPLE_RATE
    speech_rate: int = 0  # -500 to 500, 0 = normal speed
    volume: int = 80  # 0-100
    enable_subtitle: bool = False
    max_reconnects: int = NLS_RECONNECT_MAX_RETRIES


@dataclass
class CloudTTSResult:
    """Result from cloud TTS synthesis."""

    request_id: str
    total_chunks: int
    duration_ms: int
    voice: str
    text: str = ""


class CloudTTSClient:
    """Async client for Alibaba Cloud NLS streaming TTS.

    Wraps the raw WebSocket protocol (not the SDK) for maximum control
    and minimal dependency footprint.

    Usage::

        client = CloudTTSClient(config)
        await client.connect()

        client.synthesize(
            text="欢迎来到直播间",
            on_chunk=lambda request_id, seq, pcm: print(f"chunk {seq}"),
            on_complete=lambda result: print(f"done: {result.duration_ms}ms"),
            on_error=lambda code, msg: print(f"error {code}: {msg}"),
        )
    """

    def __init__(self, config: CloudTTSConfig) -> None:
        self.config = config
        self._ws: ClientConnection | None = None
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._connected: bool = False

    # ── Connection ────────────────────────────────────────────

    async def connect(self) -> None:
        """Establish WebSocket connection with NLS gateway."""
        token = await self._get_token()
        ws_url = f"{self.config.endpoint}?token={token}"

        logger.info("nls.connecting", endpoint=self.config.endpoint)

        try:
            self._ws = await websockets.connect(
                ws_url,
                ping_interval=30,
                ping_timeout=10,
                max_size=2**24,  # 16MB max message
                close_timeout=5,
            )
            self._connected = True
            logger.info("nls.connected")
        except Exception as e:
            logger.error("nls.connect_failed", error=str(e))
            raise ConnectionError(f"Failed to connect to NLS gateway: {e}") from e

    async def disconnect(self) -> None:
        """Close the WebSocket gracefully."""
        self._connected = False
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        logger.info("nls.disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None

    # ── Token Management ──────────────────────────────────────

    async def _get_token(self) -> str:
        """Get or refresh NLS access token."""
        now = time.time()
        if self._token and now < self._token_expires_at - 60:
            return self._token

        # Generate HMAC-SHA1 token
        # Token format: base64(payload + ":" + sha1(payload, secret))
        expire_time = int(now) + NLS_TOKEN_EXPIRE_SECONDS
        payload = json.dumps({"exp": expire_time, "iss": self.config.access_key_id})
        payload_b64 = base64.b64encode(payload.encode()).decode()

        signature = hmac.new(
            self.config.access_key_secret.encode(),
            payload_b64.encode(),
            hashlib.sha1,
        ).digest()
        signature_b64 = base64.b64encode(signature).decode()

        self._token = f"{payload_b64}.{signature_b64}"
        self._token_expires_at = expire_time
        logger.debug("nls.token_refreshed", expires_at=expire_time)
        return self._token

    # ── Streaming Synthesis ───────────────────────────────────

    async def synthesize(
        self,
        text: str,
        on_chunk: Callable[[str, int, bytes], None],
        on_complete: Callable[[CloudTTSResult], None],
        on_error: Callable[[int, str], None],
        request_id: str | None = None,
    ) -> None:
        """Streaming TTS synthesis over WebSocket.

        Sends text → receives binary PCM chunks → calls on_chunk per chunk.
        """
        if not self.is_connected:
            on_error(6001, "NLS client not connected")
            return

        request_id = request_id or f"nls-{uuid.uuid4().hex[:12]}"
        task_id = str(uuid.uuid4())

        logger.info(
            "nls.synthesize.start",
            request_id=request_id,
            task_id=task_id,
            text_len=len(text),
            voice=self.config.voice,
        )

        try:
            # 1. Send StartSynthesis command
            start_cmd = self._build_start_command(text, task_id)
            await self._ws.send(json.dumps(start_cmd))

            # 2. Read server response and binary frames
            total_chunks = 0
            start_time = time.monotonic()
            synthesis_completed = False
            error_occurred = False

            async for message in self._ws:
                if isinstance(message, bytes):
                    # Binary = PCM audio chunk
                    total_chunks += 1
                    on_chunk(request_id, total_chunks - 1, message)

                elif isinstance(message, str):
                    frame = json.loads(message)
                    header = frame.get("header", {})
                    msg_name = header.get("name", "")

                    if msg_name == "SynthesisStarted":
                        logger.debug(
                            "nls.synthesis.started",
                            request_id=request_id,
                            task_id=frame.get("header", {}).get("task_id", ""),
                        )

                    elif msg_name == "SynthesisCompleted":
                        synthesis_completed = True
                        elapsed_ms = int((time.monotonic() - start_time) * 1000)
                        result = CloudTTSResult(
                            request_id=request_id,
                            total_chunks=total_chunks,
                            duration_ms=elapsed_ms,
                            voice=self.config.voice,
                            text=text,
                        )
                        logger.info(
                            "nls.synthesize.complete",
                            request_id=request_id,
                            total_chunks=total_chunks,
                            duration_ms=elapsed_ms,
                        )
                        on_complete(result)
                        break

                    elif msg_name == "TaskFailed":
                        error_occurred = True
                        status = header.get("status_text", "Unknown NLS error")
                        status_code = header.get("status", -1)
                        logger.error(
                            "nls.synthesize.task_failed",
                            request_id=request_id,
                            status_code=status_code,
                            status=status,
                        )
                        on_error(6002, f"NLS synthesis failed: {status} (code={status_code})")
                        break

                    elif msg_name == "SynthesisResultChanged":
                        # Optional: subtitle/word-level timestamp info
                        pass

                    else:
                        logger.debug(
                            "nls.unknown_frame",
                            request_id=request_id,
                            msg_name=msg_name,
                        )

            if not synthesis_completed and not error_occurred:
                on_error(6003, "Synthesis connection closed without completion")

        except websockets.ConnectionClosed as e:
            logger.warning(
                "nls.connection_closed",
                request_id=request_id,
                code=e.code,
                reason=e.reason,
            )
            if not error_occurred:
                on_error(6004, f"NLS connection closed: {e.reason} (code={e.code})")

        except Exception as e:
            logger.exception("nls.synthesize.exception", request_id=request_id)
            on_error(6005, f"NLS client error: {e}")

    def _build_start_command(self, text: str, task_id: str) -> dict:
        """Build the StartSynthesis JSON command."""
        return {
            "header": {
                "message_id": str(uuid.uuid4()),
                "task_id": task_id,
                "namespace": "SpeechSynthesizer",
                "name": "StartSynthesis",
                "appkey": self.config.app_key,
            },
            "payload": {
                "text": text,
                "voice": self.config.voice,
                "format": "pcm",
                "sample_rate": str(self.config.sample_rate),
                "volume": self.config.volume,
                "speech_rate": self.config.speech_rate,
                "enable_subtitle": self.config.enable_subtitle,
            },
            "context": {},
        }

    def _build_stop_command(self, task_id: str) -> dict:
        """Build the StopSynthesis JSON command."""
        return {
            "header": {
                "message_id": str(uuid.uuid4()),
                "task_id": task_id,
                "namespace": "SpeechSynthesizer",
                "name": "StopSynthesis",
                "appkey": self.config.app_key,
            },
            "payload": {},
            "context": {},
        }
