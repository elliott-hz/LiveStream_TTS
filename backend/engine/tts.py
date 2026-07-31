"""CosyVoice TTS API 客户端"""
import httpx
from backend.config import settings


async def synthesize(text: str, speed: float = 1.0) -> bytes:
    """合成语音，返回 WAV bytes"""
    if settings.mock_external_api:
        return b"\x00" * 1024  # 假音频

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://cosyvoice.aliyuncs.com/api/v1/tts",
            headers={"Authorization": f"Bearer {settings.cosyvoice_api_key}"},
            json={"text": text, "speed": speed, "format": "wav"},
        )
        return resp.content
