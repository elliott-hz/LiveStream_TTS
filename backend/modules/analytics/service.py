from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.analytics import LiveSession, DanmakuRecord


async def list_sessions(db: AsyncSession, room_id: str | None = None) -> list[LiveSession]:
    q = select(LiveSession).order_by(LiveSession.start_time.desc())
    if room_id:
        q = q.where(LiveSession.room_id == room_id)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_session(db: AsyncSession, session_id: str) -> LiveSession | None:
    return await db.get(LiveSession, session_id)


async def get_danmaku_stats(db: AsyncSession, session_id: str) -> dict:
    """单场直播的弹幕统计"""
    total = await db.scalar(
        select(func.count(DanmakuRecord.id)).where(DanmakuRecord.session_id == session_id)
    )
    ai_replied = await db.scalar(
        select(func.count(DanmakuRecord.id))
        .where(DanmakuRecord.session_id == session_id)
        .where(DanmakuRecord.ai_reply != "")
    )
    return {
        "total": total or 0,
        "ai_replied": ai_replied or 0,
        "ai_reply_rate": f"{(ai_replied / total * 100):.1f}%" if total else "0%",
    }
