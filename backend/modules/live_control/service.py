"""直播中控台：WebSocket 弹幕 + 指标推送"""

import asyncio
import json
from datetime import datetime

from fastapi import WebSocket


class LiveControlHub:
    """
    管理所有直播间的 WebSocket 连接。
    单进程内用 dict + asyncio.Queue，不依赖 Redis。
    """

    def __init__(self):
        self._rooms: dict[str, set[WebSocket]] = {}
        self._danmaku_queues: dict[str, asyncio.Queue] = {}

    def get_or_create_queue(self, room_id: str) -> asyncio.Queue:
        if room_id not in self._danmaku_queues:
            self._danmaku_queues[room_id] = asyncio.Queue()
        return self._danmaku_queues[room_id]

    async def connect(self, room_id: str, ws: WebSocket):
        await ws.accept()
        self._rooms.setdefault(room_id, set()).add(ws)

    def disconnect(self, room_id: str, ws: WebSocket):
        if room_id in self._rooms:
            self._rooms[room_id].discard(ws)

    async def broadcast_metrics(self, room_id: str, metrics: dict):
        """推送实时指标到该直播间所有 WebSocket"""
        if room_id not in self._rooms:
            return
        msg = json.dumps({"type": "metrics", **metrics}, ensure_ascii=False)
        dead = []
        for ws in self._rooms[room_id]:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room_id, ws)

    async def broadcast_danmaku(self, room_id: str, danmaku: dict):
        """推送单条弹幕"""
        if room_id not in self._rooms:
            return
        msg = json.dumps({"type": "danmaku", **danmaku}, ensure_ascii=False)
        dead = []
        for ws in self._rooms[room_id]:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room_id, ws)

    async def send_to_room(self, room_id: str, msg: dict):
        """发送任意消息给直播间所有连接"""
        if room_id not in self._rooms:
            return
        text = json.dumps(msg, ensure_ascii=False)
        dead = []
        for ws in self._rooms[room_id]:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room_id, ws)

    async def process_danmaku_loop(self, room_id: str, db_session_factory):
        """
        弹幕处理循环：从淘宝拉弹幕 → NLP → LLM → 回复 → 广播到前端。
        在 BackgroundTasks 中启动。
        """
        from backend.adapters.taobao import taobao
        from backend.engine.nlp import Danmaku, should_reply, classify
        from backend.engine.llm import chat

        while room_id in self._danmaku_queues:
            try:
                # 从淘宝拉弹幕
                danmakus = await taobao.get_danmaku(room_id)
                for d in danmakus:
                    dm = Danmaku(user_name=d.get("user_name", ""), content=d.get("content", ""))

                    # 广播到前端
                    await self.broadcast_danmaku(room_id, {
                        "user": dm.user_name,
                        "content": dm.content,
                        "time": dm.time,
                    })

                    # NLP 判断是否回复
                    if should_reply(dm):
                        intent = classify(dm.content)
                        # LLM 生成回复
                        reply = await chat(
                            prompt=f"观众问：{dm.content}\n请用亲切的直播语气回复，50字以内。",
                            system_prompt="你是一个淘宝直播间的主播助手，负责回答观众关于商品的问题。",
                        )
                        # 发送到淘宝
                        await taobao.send_reply(room_id, reply)
                        # 广播 AI 回复到前端
                        await self.send_to_room(room_id, {
                            "type": "ai_reply",
                            "content": reply,
                            "reply_to": dm.user_name,
                        })

                await asyncio.sleep(5)  # 5 秒轮询

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5)


# 全局单例
hub = LiveControlHub()
