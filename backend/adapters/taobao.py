"""淘宝平台适配器"""

import httpx
from backend.adapters.base import PlatformAdapter
from backend.config import settings


class TaobaoAdapter(PlatformAdapter):
    platform = "taobao"

    async def get_danmaku(self, room_id: str) -> list[dict]:
        """
        通过淘宝开放平台 API 获取弹幕。
        PoC 阶段：如果淘宝 API 不可用，可从 WebSocket 采集。
        """
        # 淘宝弹幕 API (简化示例)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://eco.taobao.com/router/rest",
                params={
                    "method": "taobao.live.danmaku.query",
                    "app_key": settings.taobao_app_key,
                    "room_id": room_id,
                },
            )
            data = resp.json()
            return data.get("danmaku_list", [])

    async def send_reply(self, room_id: str, content: str, reply_to: str = ""):
        """发送文字回复到淘宝聊天区"""
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                "https://eco.taobao.com/router/rest",
                params={
                    "method": "taobao.live.message.send",
                    "app_key": settings.taobao_app_key,
                    "room_id": room_id,
                    "content": content,
                },
            )

    async def pop_product(self, room_id: str, product_id: str):
        """弹出商品卡片"""
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                "https://eco.taobao.com/router/rest",
                params={
                    "method": "taobao.live.product.pop",
                    "app_key": settings.taobao_app_key,
                    "room_id": room_id,
                    "product_id": product_id,
                },
            )

    @property
    def capabilities(self) -> dict:
        return {
            "stream": True,
            "danmaku": True,
            "product_pop": True,
            "reply": True,
        }


# 全局单例
taobao = TaobaoAdapter()
