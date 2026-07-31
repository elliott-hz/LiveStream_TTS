"""阿里云 ASR API 客户端"""
import httpx
from backend.config import settings


async def transcribe(video_path: str) -> str:
    """调用阿里云 ASR API，返回完整文稿"""
    if settings.mock_external_api:
        return "今天给大家带来这款法式碎花连衣裙，100%纯棉面料，亲肤透气。有S到XL全尺码。现在下单只要199。接下来看这款冰丝防晒袖套，UPF50+防晒指数..."

    async with httpx.AsyncClient(timeout=120) as client:
        with open(video_path, "rb") as f:
            resp = await client.post(
                "https://nlsapi.aliyun.com/recognize",
                headers={"Authorization": f"Bearer {settings.aliyun_secret}"},
                content=f.read(),
            )
        return resp.json().get("result", "")
