"""
FFmpeg 预处理 — 本地零成本
  - 场景检测 (shot detection) → 粗切时间点
  - 关键帧抽取 (1张/30秒)
  - 音频分离 → wav
"""

import os
import subprocess
from dataclasses import dataclass, field


@dataclass
class PreprocessResult:
    duration: float                   # 视频总时长(秒)
    scene_changes: list[float]        # 场景切换时间点
    keyframes: list[str]              # 关键帧文件路径列表
    audio_path: str                   # 分离出的音频 wav


def preprocess(video_path: str, output_dir: str, frame_interval: int = 30) -> PreprocessResult:
    """
    对视频做预处理，返回结构化数据。

    Args:
        video_path: 输入视频路径
        output_dir: 输出目录 (存放 keyframes 和 audio)
        frame_interval: 抽帧间隔(秒), 默认 30
    """
    os.makedirs(output_dir, exist_ok=True)
    duration = _get_duration(video_path)
    scene_changes = _detect_scenes(video_path)
    keyframes = _extract_keyframes(video_path, output_dir, frame_interval, duration)
    audio_path = _extract_audio(video_path, output_dir)

    return PreprocessResult(
        duration=duration,
        scene_changes=scene_changes,
        keyframes=keyframes,
        audio_path=audio_path,
    )


def _get_duration(video_path: str) -> float:
    """获取视频时长(秒)"""
    result = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ], capture_output=True, text=True, timeout=15)
    return float(result.stdout.strip()) if result.stdout.strip() else 0.0


def _detect_scenes(video_path: str, threshold: float = 0.3) -> list[float]:
    """
    FFmpeg scene detection: 检测画面切换点。
    threshold 越小越敏感 (0.3 = 30%像素变化算切换)。
    """
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-filter:v", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null", "-",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        times = []
        for line in result.stderr.split("\n"):
            if "pts_time:" in line:
                t = float(line.split("pts_time:")[1].split()[0])
                times.append(t)
        return sorted(set(times))
    except Exception:
        return []


def _extract_keyframes(video_path: str, output_dir: str, interval: int, duration: float) -> list[str]:
    """每 N 秒抽一帧，返回图片路径列表"""
    paths = []
    for sec in range(0, int(duration), interval):
        filename = f"frame_{sec:04d}.jpg"
        out = os.path.join(output_dir, filename)
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(sec),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            out,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        if os.path.exists(out):
            paths.append(out)
        else:
            break
    return paths


def _extract_audio(video_path: str, output_dir: str) -> str:
    """分离音频轨道"""
    out = os.path.join(output_dir, "audio.wav")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        out,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    return out
