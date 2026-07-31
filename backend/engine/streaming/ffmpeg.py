"""FFmpeg 进程管理：RTMP 推流 + 音频混流"""

import asyncio
import subprocess
from pathlib import Path


class StreamProcess:
    """管理一个 FFmpeg 推流子进程"""

    def __init__(self, rtmp_url: str, playlist_file: str):
        self.rtmp_url = rtmp_url
        self.playlist_file = playlist_file
        self.process: subprocess.Popen | None = None

    def start(self):
        """启动 FFmpeg 循环推流"""
        cmd = [
            "ffmpeg",
            "-re",                          # 按帧率读取，模拟实时
            "-stream_loop", "-1",           # 无限循环
            "-f", "concat",
            "-safe", "0",
            "-i", self.playlist_file,
            "-c", "copy",
            "-f", "flv",
            self.rtmp_url,
        ]
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def stop(self):
        """优雅关闭"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None


# 全局字典：room_id → StreamProcess
_active_streams: dict[str, StreamProcess] = {}


async def start_stream(room_id: str, rtmp_url: str, playlist: list, concat_file: str):
    """开播"""
    if room_id in _active_streams and _active_streams[room_id].is_running:
        raise RuntimeError(f"Room {room_id} is already streaming")

    # 1. 生成 concat 播放列表文件
    from backend.engine.streaming.playlist import to_concat_file
    to_concat_file(playlist, concat_file)

    # 2. 启动 FFmpeg
    proc = StreamProcess(rtmp_url, concat_file)
    proc.start()
    _active_streams[room_id] = proc

    # 3. 等待一小段时间确认推流没挂
    await asyncio.sleep(1)
    if not proc.is_running:
        raise RuntimeError("FFmpeg failed to start")


async def stop_stream(room_id: str):
    """停播"""
    proc = _active_streams.pop(room_id, None)
    if proc:
        proc.stop()


def stream_health(room_id: str) -> dict | None:
    """推流健康检查"""
    proc = _active_streams.get(room_id)
    if not proc:
        return None
    return {
        "is_running": proc.is_running,
        "pid": proc.process.pid if proc.process else None,
    }
