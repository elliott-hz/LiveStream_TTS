"""阿里云智能媒体 API — 场景/商品边界检测"""
import httpx
from backend.config import settings


async def detect_scenes(video_path: str) -> list[dict]:
    """检测商品边界，返回分段列表"""
    if settings.mock_external_api:
        return [
            {"start": 0.0, "end": 15.0},
            {"start": 15.0, "end": 30.0},
        ]

    async with httpx.AsyncClient(timeout=300) as client:
        with open(video_path, "rb") as f:
            resp = await client.post(
                "https://imm.aliyuncs.com/api/v1/scene/detect",
                headers={"Authorization": f"Bearer {settings.aliyun_secret}"},
                content=f.read(),
            )
        data = resp.json()
        return data.get("segments", [])
