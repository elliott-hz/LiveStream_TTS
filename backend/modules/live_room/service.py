import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.room import LiveRoom, RoomSchedule
from backend.models.video import LiveVideo, LiveVideoClip, VideoSegment
from backend.modules.live_room.schemas import RoomCreate, RoomUpdate, ScheduleIn
from backend.engine.streaming import ffmpeg, playlist


async def list_rooms(db: AsyncSession) -> list[LiveRoom]:
    result = await db.execute(select(LiveRoom).order_by(LiveRoom.created_at.desc()))
    return list(result.scalars().all())


async def get_room(db: AsyncSession, room_id: str) -> LiveRoom | None:
    return await db.get(LiveRoom, room_id)


async def create_room(db: AsyncSession, data: RoomCreate) -> LiveRoom:
    room = LiveRoom(name=data.name, platform=data.platform, rtmp_url=data.rtmp_url)
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room


async def update_room(db: AsyncSession, room_id: str, data: RoomUpdate) -> LiveRoom | None:
    room = await get_room(db, room_id)
    if not room:
        return None
    if data.name is not None:
        room.name = data.name
    if data.rtmp_url is not None:
        room.rtmp_url = data.rtmp_url
    await db.commit()
    await db.refresh(room)
    return room


async def delete_room(db: AsyncSession, room_id: str) -> bool:
    room = await get_room(db, room_id)
    if not room or room.status == "live":
        return False
    await db.delete(room)
    await db.commit()
    return True


async def attach_video(db: AsyncSession, room_id: str, live_video_id: str) -> LiveRoom | None:
    room = await get_room(db, room_id)
    video = await db.get(LiveVideo, live_video_id)
    if not room or not video:
        return None
    room.attached_video_id = live_video_id
    await db.commit()
    await db.refresh(room)
    return room


async def start_room(db: AsyncSession, room_id: str) -> LiveRoom:
    room = await get_room(db, room_id)
    if not room:
        raise ValueError("Room not found")
    if not room.attached_video_id:
        raise ValueError("No video attached")
    if room.status == "live":
        raise ValueError("Room is already live")

    # 加载编排好的切片，生成播放列表
    live_video = await db.get(LiveVideo, room.attached_video_id)
    # 需要 eager load clips
    from sqlalchemy.orm import selectinload
    live_video = await db.get(LiveVideo, room.attached_video_id, options=[selectinload(LiveVideo.clips)])
    if not live_video or not live_video.clips:
        raise ValueError("Live video has no clips")

    clip_data = []
    for clip in live_video.clips:
        seg = await db.get(VideoSegment, clip.segment_id)
        if seg and seg.clip_path:
            clip_data.append({
                "segment_id": seg.id,
                "clip_path": seg.clip_path,
                "weight": clip.weight,
                "pause_after": clip.pause_after,
                "pause_content": clip.pause_content,
            })

    pl = playlist.generate(clip_data, play_mode=live_video.play_mode)

    # 生成 concat 文件
    concat_file = os.path.join(settings.video_dir, f"playlist_{room_id}.txt")

    # 启动推流
    await ffmpeg.start_stream(room_id, room.rtmp_url, pl, concat_file)

    room.status = "live"
    await db.commit()
    await db.refresh(room)
    return room


async def stop_room(db: AsyncSession, room_id: str) -> LiveRoom | None:
    room = await get_room(db, room_id)
    if not room or room.status != "live":
        return None

    await ffmpeg.stop_stream(room_id)

    room.status = "idle"
    await db.commit()
    await db.refresh(room)
    return room


async def get_schedule(db: AsyncSession, room_id: str) -> RoomSchedule | None:
    result = await db.execute(select(RoomSchedule).where(RoomSchedule.room_id == room_id))
    return result.scalar_one_or_none()


async def set_schedule(db: AsyncSession, room_id: str, data: ScheduleIn) -> RoomSchedule:
    schedule = await get_schedule(db, room_id)
    if not schedule:
        schedule = RoomSchedule(room_id=room_id)
        db.add(schedule)
    schedule.enabled = data.enabled
    schedule.start_time = data.start_time
    schedule.end_time = data.end_time
    await db.commit()
    await db.refresh(schedule)
    return schedule
