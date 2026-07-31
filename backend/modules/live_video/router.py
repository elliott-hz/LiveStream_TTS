from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import get_db
from backend.modules.live_video import service
from backend.modules.live_video.schemas import (
    LiveVideoCreate, LiveVideoUpdate, LiveVideoOut, LiveVideoClipIn, LiveVideoClipOut,
)

router = APIRouter(prefix="/api/live-videos", tags=["live_videos"])


@router.get("", response_model=list[LiveVideoOut])
async def list_videos(db: AsyncSession = Depends(get_db)):
    return await service.list_live_videos(db)


@router.get("/{video_id}", response_model=LiveVideoOut)
async def get_video(video_id: str, db: AsyncSession = Depends(get_db)):
    v = await service.get_live_video(db, video_id)
    if not v:
        raise HTTPException(404, "Live video not found")
    return v


@router.post("", response_model=LiveVideoOut, status_code=201)
async def create_video(data: LiveVideoCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_live_video(db, data)


@router.put("/{video_id}", response_model=LiveVideoOut)
async def update_video(video_id: str, data: LiveVideoUpdate, db: AsyncSession = Depends(get_db)):
    v = await service.update_live_video(db, video_id, data)
    if not v:
        raise HTTPException(404, "Live video not found")
    return v


@router.post("/{video_id}/clips", response_model=LiveVideoClipOut, status_code=201)
async def add_clip(video_id: str, data: LiveVideoClipIn, db: AsyncSession = Depends(get_db)):
    try:
        return await service.add_clip(db, video_id, data)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/{video_id}/clips/{clip_id}", status_code=204)
async def remove_clip(video_id: str, clip_id: str, db: AsyncSession = Depends(get_db)):
    ok = await service.remove_clip(db, clip_id)
    if not ok:
        raise HTTPException(404, "Clip not found")


@router.put("/{video_id}/clips/reorder", status_code=200)
async def reorder_clips(video_id: str, clip_ids: list[str], db: AsyncSession = Depends(get_db)):
    await service.reorder_clips(db, video_id, clip_ids)
    return {"ok": True}
