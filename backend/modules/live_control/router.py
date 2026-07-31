import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import get_db
from backend.modules.live_control.service import hub
from backend.engine.streaming.ffmpeg import stream_health
from backend.models.room import LiveRoom

router = APIRouter(tags=["live_control"])


@router.websocket("/ws/live/{room_id}")
async def live_control_ws(ws: WebSocket, room_id: str):
    await hub.connect(room_id, ws)

    # 启动弹幕处理循环（后台）
    danmaku_task = asyncio.create_task(
        hub.process_danmaku_loop(room_id, None)
    )

    try:
        while True:
            # 接收前端控制指令
            data = await ws.receive_text()
            msg = json.loads(data)

            action = msg.get("type")
            if action == "pop_product":
                await hub.send_to_room(room_id, {"type": "pop_product", "product_id": msg.get("product_id")})
            elif action == "switch_product":
                await hub.send_to_room(room_id, {"type": "product_change"})
            elif action == "manual_reply":
                await hub.send_to_room(room_id, {"type": "manual_reply", "content": msg.get("content")})
            elif action == "emergency_stop":
                await hub.send_to_room(room_id, {"type": "emergency_stop"})
                break

    except WebSocketDisconnect:
        pass
    finally:
        danmaku_task.cancel()
        hub.disconnect(room_id, ws)


@router.get("/api/stream-health/{room_id}")
async def get_stream_health(room_id: str):
    health = stream_health(room_id)
    if not health:
        return {"room_id": room_id, "is_running": False}
    return {"room_id": room_id, **health}
