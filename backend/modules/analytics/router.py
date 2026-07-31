from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import get_db
from backend.modules.analytics import service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/sessions")
async def list_sessions(room_id: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    return await service.list_sessions(db, room_id)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    s = await service.get_session(db, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    return s


@router.get("/sessions/{session_id}/danmaku-stats")
async def get_danmaku_stats(session_id: str, db: AsyncSession = Depends(get_db)):
    return await service.get_danmaku_stats(db, session_id)
