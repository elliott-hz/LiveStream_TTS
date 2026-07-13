"""
TTS Platform — POC 入口
将所有模块 (M1-M10) 装配为一个系统，启动 WebSocket + gRPC + REST 服务。

完整管线流:
  Client text
    → M1 Gateway
    → M2 Session (状态管理)
    → M3 TextPreprocessor (TN)
    → M5 EmotionEngine (情感分类)
    → M4 LinguisticEngine (G2P + Prosody)
    → M6 SpeakerManager (音色加载)
    → M9 AudioCache (缓存查询)
    → M7 TTSEngine (模型推理)
    → M8 DSP (后处理)
    → M9 AudioCache (缓存写入)
    → M1 Gateway → Streaming PCM
"""

import asyncio
import base64
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path

import grpc
import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

from .audio_cache import AudioCache
from .dsp import DSP
from .emotion_engine import EmotionEngine
from .gateway import TTSGateway
from .linguistic_engine import LinguisticEngine
from .mixer import AudioMixer
from .session_manager import SessionManager
from .speaker_manager import SpeakerManager
from .text_preprocessor import TextPreprocessor
from .tts_engine import TTSEngine, CHUNK_SIZE as TTS_CHUNK_SAMPLES

# ── 注册 gRPC 生成的模块 ──
from . import tts_pb2_grpc

logger = logging.getLogger("tts-poc")

# ── 配置 ──
SAMPLE_RATE = 16000
WS_HOST = "0.0.0.0"
WS_PORT = 8765
GRPC_PORT = 50051
VOICES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "voices")


def build_pipeline_runner(
    m3: TextPreprocessor,
    m4: LinguisticEngine,
    m5: EmotionEngine,
    m6: SpeakerManager,
    m7: TTSEngine,
    m8: DSP,
    m9: AudioCache,
):
    """构建全管线异步生成器。"""

    async def run(request_id: str, text: str, voice_id: str,
                  emotion: str, speed: float):
        """执行完整合成管线，逐 chunk 产出帧。"""
        m8.reset()
        t_start = time.time()

        logger.info(f"[{request_id}] ╔═══ PIPELINE START ════════════════════════════")
        logger.info(f"[{request_id}] ║ INPUT: text=\"{text[:40]}...\", voice={voice_id}, emotion={emotion}, speed={speed}")

        # ── 1. M3: Text Normalization ──
        t0 = time.time()
        try:
            normalized = m3.process(text)
        except Exception as e:
            yield {"type": "error", "request_id": request_id, "error_code": 2001, "message": f"TN failed: {e}"}
            return
        t_m3 = time.time() - t0
        logger.info(f"[{request_id}] ║ M3 TN: {t_m3*1000:.1f}ms | \"{text[:40]}...\" → \"{normalized[:40]}...\"")

        if not normalized:
            yield {"type": "error", "request_id": request_id, "error_code": 2002, "message": "text is empty after normalization"}
            return

        # ── 2. M5: Emotion Classification ──
        t0 = time.time()
        emotion_tag = m5.classify(normalized, explicit_emotion=emotion)
        t_m5 = time.time() - t0
        logger.info(f"[{request_id}] ║ M5 Emotion: {t_m5*1000:.1f}ms | {emotion_tag.emotion}")

        # ── 3. M4: Linguistic Processing ──
        t0 = time.time()
        try:
            features = m4.process(normalized, emotion=emotion_tag.emotion, speed=speed)
        except Exception as e:
            yield {"type": "error", "request_id": request_id, "error_code": 4002, "message": f"Linguistic failed: {e}"}
            return
        t_m4 = time.time() - t0
        logger.info(f"[{request_id}] ║ M4 Linguistic: {t_m4*1000:.1f}ms | {len(features.phonemes)} phonemes, {len(features.pause_positions)} pauses")

        # ── 4. M6: Speaker Embedding ──
        t0 = time.time()
        voice = m6.get_voice(voice_id)
        if not voice:
            yield {"type": "error", "request_id": request_id, "error_code": 3001, "message": f"voice_id '{voice_id}' not found"}
            return
        embedding = m6.load_embedding(voice_id)
        t_m6 = time.time() - t0
        logger.info(f"[{request_id}] ║ M6 Speaker: {t_m6*1000:.1f}ms | {voice.name}")

        # ── 5. M9: Cache Query ──
        cache_key = AudioCache.build_key(normalized, voice_id, emotion_tag.emotion)
        t0 = time.time()
        cached_pcm = m9.get(cache_key)
        t_m9q = time.time() - t0

        if cached_pcm:
            logger.info(f"[{request_id}] ║ M9 Cache: {t_m9q*1000:.1f}ms | HIT → bypass inference")
            chunk_bytes = TTS_CHUNK_SAMPLES * 2
            total_chunks = len(cached_pcm) // chunk_bytes
            for seq in range(total_chunks):
                chunk = cached_pcm[seq * chunk_bytes:(seq + 1) * chunk_bytes]
                yield {
                    "type": "audio_chunk",
                    "request_id": request_id,
                    "sequence": seq,
                    "data": base64.b64encode(chunk).decode(),
                    "sample_rate": SAMPLE_RATE,
                }
                await asyncio.sleep(0)
            t_total = time.time() - t_start
            logger.info(f"[{request_id}] ║ DONE (CACHED): {total_chunks} chunks, {t_total*1000:.0f}ms total")
            logger.info(f"[{request_id}] ╚═══ PIPELINE END (CACHED) ════════════════════")
            yield {
                "type": "synthesis_complete",
                "request_id": request_id,
                "total_chunks": total_chunks,
                "duration_ms": int(total_chunks * 20),
            }
            return

        logger.info(f"[{request_id}] ║ M9 Cache: {t_m9q*1000:.1f}ms | MISS")

        # ── 6-7. M7 Inference + M8 DSP ──
        full_pcm = bytearray()
        total_chunks = 0
        complete_event = asyncio.Event()
        error_result = [None]

        def on_chunk(req_id: str, seq: int, pcm: bytes):
            nonlocal total_chunks, full_pcm
            processed = m8.process_chunk(pcm)
            if processed:
                full_pcm.extend(processed)
                total_chunks += 1

        def on_complete(result):
            complete_event.set()

        def on_error(code: int, msg: str):
            error_result[0] = (code, msg)
            complete_event.set()

        t0 = time.time()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: m7.synthesize_stream(
                request_id, features, emotion_tag, speed,
                on_chunk, on_complete, on_error,
            )
        )
        t_m7 = time.time() - t0
        logger.info(f"[{request_id}] ║ M7+M8: {t_m7*1000:.1f}ms | inference+DSP")

        if error_result[0]:
            logger.error(f"[{request_id}] ║ ERROR: code={error_result[0][0]}, msg={error_result[0][1]}")
            yield {
                "type": "error", "request_id": request_id,
                "error_code": error_result[0][0],
                "message": error_result[0][1],
            }
            return

        # ── 8. M9: Cache Write ──
        t0 = time.time()
        if full_pcm:
            m9.set(cache_key, bytes(full_pcm))
        t_m9w = time.time() - t0
        logger.info(f"[{request_id}] ║ M9 Cache WRITE: {t_m9w*1000:.1f}ms | {len(full_pcm)} bytes")

        # ── Stream Output ──
        if full_pcm:
            chunk_bytes = TTS_CHUNK_SAMPLES * 2
            for seq in range(0, len(full_pcm), chunk_bytes):
                chunk = full_pcm[seq:seq + chunk_bytes]
                yield {
                    "type": "audio_chunk",
                    "request_id": request_id,
                    "sequence": seq // chunk_bytes,
                    "data": base64.b64encode(chunk).decode(),
                    "sample_rate": SAMPLE_RATE,
                }
                await asyncio.sleep(0)

        t_total = time.time() - t_start
        logger.info(f"[{request_id}] ║ TIMING: M3={t_m3*1000:.0f}ms M5={t_m5*1000:.0f}ms M4={t_m4*1000:.0f}ms M6={t_m6*1000:.0f}ms M7+M8={t_m7*1000:.0f}ms M9W={t_m9w*1000:.0f}ms TOTAL={t_total*1000:.0f}ms")
        logger.info(f"[{request_id}] ║ RESULT: {total_chunks} chunks, {len(full_pcm)} bytes PCM")
        logger.info(f"[{request_id}] ╚═══ PIPELINE END ═══════════════════════════════════")
        yield {
            "type": "synthesis_complete",
            "request_id": request_id,
            "total_chunks": total_chunks,
            "duration_ms": int(total_chunks * 20),
        }

    return run


def create_app() -> FastAPI:
    """创建 FastAPI 应用，装配所有模块。"""
    # ── 初始化模块 ──
    m3 = TextPreprocessor()
    m4 = LinguisticEngine(sample_rate=SAMPLE_RATE)
    m5 = EmotionEngine()
    m6 = SpeakerManager(voices_dir=VOICES_DIR)
    m7 = TTSEngine(sample_rate=SAMPLE_RATE)
    m8 = DSP(sample_rate=SAMPLE_RATE)
    m9 = AudioCache()
    _m10 = AudioMixer()  # POC 暂不接入 Mixer

    sm = SessionManager()
    pipeline_runner = build_pipeline_runner(m3, m4, m5, m6, m7, m8, m9)
    gateway = TTSGateway(sm, pipeline_runner)

    # ── FastAPI ──
    app = FastAPI(title="TTS Platform POC", version="1.0.0-poc")

    # 挂载 REST 路由（含 health + voices）
    app.include_router(gateway.build_router(m6))

    # ── WebSocket 端点 ──
    @app.websocket("/ws/v1/tts")
    async def tts_ws(ws: WebSocket):
        await gateway.handle_websocket(ws)

    # ── 静态页面 ──
    static_dir = Path(__file__).parent.parent / "static"
    index_html = static_dir / "index.html"

    @app.get("/")
    async def index():
        if index_html.exists():
            return HTMLResponse(index_html.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>TTS Platform POC</h1><p>index.html not found</p>")

    @app.get("/static/{filename}")
    async def static_file(filename: str):
        filepath = static_dir / filename
        if filepath.exists():
            return HTMLResponse(filepath.read_text(encoding="utf-8"))
        return HTMLResponse("", status_code=404)

    return app


def run_grpc_server(gateway: TTSGateway):
    """启动 gRPC 服务器（独立线程 + 独立事件循环）。"""
    server = grpc.aio.server()
    tts_pb2_grpc.add_TTSServicer_to_server(gateway.grpc_servicer(), server)
    listen_addr = f"0.0.0.0:{GRPC_PORT}"
    server.add_insecure_port(listen_addr)
    logger.info(f"gRPC server listening on {listen_addr}")
    return server


def _start_grpc(gateway: TTSGateway):
    """在独立线程中用新事件循环启动 gRPC。"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server = run_grpc_server(gateway)
    loop.run_until_complete(server.start())
    loop.run_forever()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(name)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # 创建 FastAPI app（会初始化所有模块）
    app = create_app()

    # 提取 gateway 实例以启动 gRPC
    # gateway 被闭包捕获在 app 中，这里通过全局变量获取
    # 简化处理：直接重新装配 gateway 用于 gRPC
    m3 = TextPreprocessor()
    m4 = LinguisticEngine(sample_rate=SAMPLE_RATE)
    m5 = EmotionEngine()
    m6 = SpeakerManager(voices_dir=VOICES_DIR)
    m7 = TTSEngine(sample_rate=SAMPLE_RATE)
    m8 = DSP(sample_rate=SAMPLE_RATE)
    m9 = AudioCache()
    sm = SessionManager()
    pipeline_runner = build_pipeline_runner(m3, m4, m5, m6, m7, m8, m9)
    grpc_gateway = TTSGateway(sm, pipeline_runner)

    # 启动 gRPC（独立线程 + 独立事件循环）
    grpc_thread = threading.Thread(target=_start_grpc, args=(grpc_gateway,), daemon=True)
    grpc_thread.start()

    logger.info("=" * 50)
    logger.info("TTS Platform POC starting...")
    logger.info(f"  WebSocket → ws://{WS_HOST}:{WS_PORT}/ws/v1/tts")
    logger.info(f"  gRPC     → {WS_HOST}:{GRPC_PORT}")
    logger.info(f"  REST     → http://{WS_HOST}:{WS_PORT}/api/v1/health")
    logger.info(f"  Voices   → http://{WS_HOST}:{WS_PORT}/api/v1/voices")
    logger.info("=" * 50)

    # 启动 Web 服务
    uvicorn.run(app, host=WS_HOST, port=WS_PORT, log_level="info")


if __name__ == "__main__":
    main()
