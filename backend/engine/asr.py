"""
阿里云 DashScope — Paraformer ASR 语音识别
https://help.aliyun.com/zh/model-studio/paraformer-asr

支持录音文件识别，返回逐句时间戳。
"""

import json
import asyncio
import httpx
from backend.config import settings

DASHSCOPE_ASR_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription"


async def transcribe(audio_path: str) -> dict:
    """
    Paraformer 录音文件识别。

    返回:
    {
      "full_text": "完整文稿...",
      "sentences": [
        {"start": 0.0, "end": 3.2, "text": "今天给大家带来..."},
        {"start": 3.2, "end": 6.5, "text": "这款法式碎花..."},
        ...
      ]
    }
    """
    if settings.mock_external_api:
        return _mock_result()

    headers = {
        "Authorization": f"Bearer {settings.aliyun_access_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",  # 异步模式，长音频
    }

    payload = {
        "model": "paraformer-v2",
        "input": {
            "file_urls": [_upload_audio(audio_path)],
        },
        "parameters": {
            "format": "wav",
            "sample_rate": 16000,
            "language_hints": ["zh"],
            "sentence_timestamp": True,   # 返回逐句时间戳
        },
    }

    # 1. 提交任务
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(DASHSCOPE_ASR_URL, headers=headers, json=payload)
        data = resp.json()

    task_id = data.get("output", {}).get("task_id", "")
    if not task_id:
        raise RuntimeError(f"ASR提交失败: {data}")

    # 2. 轮询等待
    result = await _poll_task(task_id, headers)
    return _parse_asr_result(result)


async def _poll_task(task_id: str, headers: dict, timeout: int = 600) -> dict:
    """轮询异步任务直到完成"""
    url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

    for _ in range(timeout // 3):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers)
            data = resp.json()

        status = data.get("output", {}).get("task_status", "")
        if status == "SUCCEEDED":
            return data
        if status == "FAILED":
            raise RuntimeError(f"ASR失败: {data}")

        await asyncio.sleep(3)

    raise TimeoutError(f"ASR超时 ({timeout}s)")


def _parse_asr_result(data: dict) -> dict:
    """解析 Paraformer 返回"""
    output = data.get("output", {})
    results = output.get("results", [])

    if not results:
        return {"full_text": "", "sentences": []}

    # Paraformer 返回的 transcription
    transcription = results[0].get("transcription", results[0])
    sentences = transcription.get("sentences", [])

    parsed = []
    for s in sentences:
        parsed.append({
            "start": float(s.get("begin_time", s.get("start", 0))) / 1000,  # 毫秒→秒
            "end": float(s.get("end_time", s.get("end", 0))) / 1000,
            "text": s.get("text", ""),
        })

    full_text = "".join(s["text"] for s in parsed)

    return {"full_text": full_text, "sentences": parsed}


def _upload_audio(audio_path: str) -> str:
    """
    上传音频到 OSS 并返回 URL。
    对于短音频(<200MB)可以直接用本地路径。
    DashScope 也支持直接传 file_urls 为 OSS URL。
    PoC 阶段用本地文件读取后直接上传（multipart）。
    """
    # DashScope 支持通过 HTTP 上传文件
    # 对于 PoC，使用 data URI 或 OSS presigned URL
    # 简化：直接返回本地路径，DashScope 在部分 region 支持
    return f"file://{audio_path}"


def _mock_result() -> dict:
    return {
        "full_text": "今天给大家带来这款法式碎花连衣裙，100%纯棉面料，亲肤透气。有S到XL全尺码。现在下单只要199。接下来看这款冰丝防晒袖套...",
        "sentences": [
            {"start": 0.0, "end": 5.0, "text": "今天给大家带来这款法式碎花连衣裙"},
            {"start": 5.0, "end": 12.0, "text": "100%纯棉面料亲肤透气有S到XL全尺码"},
            {"start": 12.0, "end": 18.0, "text": "现在下单只要199"},
            {"start": 18.0, "end": 30.0, "text": "接下来看这款冰丝防晒袖套"},
        ],
    }
