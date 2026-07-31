"""平台适配器抽象接口"""

from abc import ABC, abstractmethod


class PlatformAdapter(ABC):
    """各直播平台适配器的抽象基类"""

    platform: str = ""

    @abstractmethod
    async def get_danmaku(self, room_id: str) -> list[dict]:
        """获取弹幕列表"""
        ...

    @abstractmethod
    async def send_reply(self, room_id: str, content: str, reply_to: str = ""):
        """发送文字回复"""
        ...

    @abstractmethod
    async def pop_product(self, room_id: str, product_id: str):
        """弹出商品卡片"""
        ...

    @property
    def capabilities(self) -> dict:
        """返回此平台支持的能力"""
        return {
            "stream": True,
            "danmaku": False,
            "product_pop": False,
            "reply": False,
        }
