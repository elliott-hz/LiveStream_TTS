import os
import subprocess

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.models.video import RawVideo, VideoSegment
from backend.modules.video_asset.schemas import SegmentUpdate


async def list_videos(db: AsyncSession) -> list[RawVideo]:
    result = await db.execute(
        select(RawVideo).options(selectinload(RawVideo.segments)).order_by(RawVideo.created_at.desc())
    )
    return list(result.scalars().all())


async def get_video(db: AsyncSession, video_id: str) -> RawVideo | None:
    result = await db.execute(
        select(RawVideo).options(selectinload(RawVideo.segments)).where(RawVideo.id == video_id)
    )
    return result.scalar_one_or_none()


async def create_video(db: AsyncSession, file_name: str, file_path: str) -> RawVideo:
    video = RawVideo(file_name=file_name, file_path=file_path, parse_status="pending")
    db.add(video)
    await db.commit()
    await db.refresh(video)
    return video


async def update_segment(db: AsyncSession, segment_id: str, data: SegmentUpdate) -> VideoSegment | None:
    result = await db.execute(select(VideoSegment).where(VideoSegment.id == segment_id))
    seg = result.scalar_one_or_none()
    if not seg:
        return None
    if data.start_time is not None:
        seg.start_time = data.start_time
    if data.end_time is not None:
        seg.end_time = data.end_time
    if data.product_id is not None:
        seg.product_id = data.product_id
    if data.script is not None:
        seg.script = data.script
    await db.commit()
    await db.refresh(seg)
    return seg


async def publish_segment(db: AsyncSession, segment_id: str) -> VideoSegment | None:
    result = await db.execute(select(VideoSegment).where(VideoSegment.id == segment_id))
    seg = result.scalar_one_or_none()
    if not seg:
        return None
    seg.status = "published"
    await db.commit()
    await db.refresh(seg)
    return seg


# ---- 解析管线 (被 BackgroundTasks 调用) ----

async def parse_video_pipeline(video_id: str):
    """后台解析管线：ASR → 场景检测 → 脚本清洗 → FFmpeg 切割"""
    from backend.models.base import async_session, engine
    from backend.engine import asr, scene_detect, llm
    from sqlalchemy.ext.asyncio import AsyncSession

    async with async_session() as db:
        video = await db.get(RawVideo, video_id)
        if not video:
            return

        video.parse_status = "processing"
        await db.commit()

        try:
            # Step 1: ASR
            video.parse_progress = 20
            await db.commit()
            transcript = await asr.transcribe(video.file_path)

            # Step 2: 场景检测
            video.parse_progress = 40
            await db.commit()
            segments = await scene_detect.detect_scenes(video.file_path)

            # Step 3+4: 脚本清洗 + FFmpeg 切割
            for i, seg in enumerate(segments):
                # 脚本清洗
                raw_text = transcript[int(seg["start"]):int(seg["end"])] if transcript else ""
                script = await llm.clean_script(raw_text)

                # FFmpeg 无损切割
                clip_name = f"{video_id}_{i}.mp4"
                clip_path = os.path.join(settings.video_dir, clip_name)
                _cut_video(video.file_path, seg["start"], seg["end"], clip_path)

                # 写入 DB
                segment = VideoSegment(
                    raw_video_id=video_id,
                    start_time=seg["start"],
                    end_time=seg["end"],
                    script=script,
                    clip_path=clip_path,
                    status="pending",
                )
                db.add(segment)

                progress = 40 + int((i + 1) / len(segments) * 60)
                video.parse_progress = progress
                await db.commit()

            video.parse_status = "done"
            video.parse_progress = 100
            await db.commit()

        except Exception as e:
            video.parse_status = "done"
            video.parse_progress = 0
            await db.commit()
            raise e


def _cut_video(input_path: str, start: float, end: float, output_path: str):
    """FFmpeg 无损切割"""
    subprocess.run([
        "ffmpeg", "-y",
        "-ss", str(start),
        "-to", str(end),
        "-i", input_path,
        "-c", "copy",
        output_path,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
