import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.base import get_db
from backend.modules.video_asset import service
from backend.modules.video_asset.schemas import RawVideoOut, SegmentOut, SegmentUpdate

router = APIRouter(prefix="/api/video-assets", tags=["video_assets"])


@router.get("", response_model=list[RawVideoOut])
async def list_videos(db: AsyncSession = Depends(get_db)):
    return await service.list_videos(db)


@router.get("/{video_id}", response_model=RawVideoOut)
async def get_video(video_id: str, db: AsyncSession = Depends(get_db)):
    v = await service.get_video(db, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    return v


@router.post("/upload", response_model=RawVideoOut, status_code=201)
async def upload_video(file: UploadFile, bg: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    # 保存到本地磁盘
    os.makedirs(settings.video_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "video.mp4")[1]
    file_name = f"{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(settings.video_dir, file_name)

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 创建记录
    video = await service.create_video(db, file_name=file.filename or file_name, file_path=file_path)

    # 后台解析
    bg.add_task(service.parse_video_pipeline, video.id)

    return video


@router.put("/segments/{segment_id}", response_model=SegmentOut)
async def update_segment(segment_id: str, data: SegmentUpdate, db: AsyncSession = Depends(get_db)):
    seg = await service.update_segment(db, segment_id, data)
    if not seg:
        raise HTTPException(404, "Segment not found")
    return seg


@router.post("/segments/{segment_id}/publish", response_model=SegmentOut)
async def publish_segment(segment_id: str, db: AsyncSession = Depends(get_db)):
    seg = await service.publish_segment(db, segment_id)
    if not seg:
        raise HTTPException(404, "Segment not found")
    return seg
