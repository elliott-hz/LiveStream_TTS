"""AutoDL 4090 Wav2Lip HTTP 客户端"""
import httpx
from backend.config import settings


async def sync_mouth(audio_path: str, face_path: str) -> bytes:
    """调用 Wav2Lip 服务，返回口型帧"""
    if settings.mock_external_api:
        return b"\x00" * 2048  # 假视频帧

    async with httpx.AsyncClient(timeout=60) as client:
        data = httpx.FormData()
        with open(audio_path, "rb") as f:
            data.add_field("audio", f)
        with open(face_path, "rb") as f:
            data.add_field("face", f)
        resp = await client.post(f"{settings.wav2lip_url}/sync", content=data)
        return resp.content
