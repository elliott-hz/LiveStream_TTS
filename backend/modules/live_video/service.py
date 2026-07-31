from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.video import LiveVideo, LiveVideoClip, VideoSegment
from backend.modules.live_video.schemas import LiveVideoCreate, LiveVideoUpdate, LiveVideoClipIn


async def list_live_videos(db: AsyncSession) -> list[LiveVideo]:
    result = await db.execute(
        select(LiveVideo).options(selectinload(LiveVideo.clips)).order_by(LiveVideo.created_at.desc())
    )
    return list(result.scalars().all())


async def get_live_video(db: AsyncSession, video_id: str) -> LiveVideo | None:
    result = await db.execute(
        select(LiveVideo).options(selectinload(LiveVideo.clips)).where(LiveVideo.id == video_id)
    )
    return result.scalar_one_or_none()


async def create_live_video(db: AsyncSession, data: LiveVideoCreate) -> LiveVideo:
    video = LiveVideo(name=data.name, play_mode=data.play_mode)
    db.add(video)
    await db.commit()
    await db.refresh(video)
    return video


async def update_live_video(db: AsyncSession, video_id: str, data: LiveVideoUpdate) -> LiveVideo | None:
    video = await get_live_video(db, video_id)
    if not video:
        return None
    if data.name is not None:
        video.name = data.name
    if data.play_mode is not None:
        video.play_mode = data.play_mode
    await db.commit()
    await db.refresh(video)
    return video


async def add_clip(db: AsyncSession, video_id: str, data: LiveVideoClipIn) -> LiveVideoClip:
    # 验证 segment 存在
    seg = await db.get(VideoSegment, data.segment_id)
    if not seg:
        raise ValueError(f"Segment {data.segment_id} not found")

    clip = LiveVideoClip(
        live_video_id=video_id,
        segment_id=data.segment_id,
        sort_order=data.sort_order,
        weight=data.weight,
        pause_after=data.pause_after,
        pause_content=data.pause_content,
        closeup=data.closeup,
        transition=data.transition,
        overlay=data.overlay,
        script_override=data.script_override,
    )
    db.add(clip)
    await db.commit()
    await db.refresh(clip)
    return clip


async def remove_clip(db: AsyncSession, clip_id: str) -> bool:
    clip = await db.get(LiveVideoClip, clip_id)
    if not clip:
        return False
    await db.delete(clip)
    await db.commit()
    return True


async def reorder_clips(db: AsyncSession, video_id: str, clip_ids: list[str]):
    """拖拽排序：按 clip_ids 顺序更新 sort_order"""
    for i, cid in enumerate(clip_ids):
        clip = await db.get(LiveVideoClip, cid)
        if clip and clip.live_video_id == video_id:
            clip.sort_order = i
    await db.commit()
