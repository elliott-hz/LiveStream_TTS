from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import get_db
from backend.modules.live_room import service
from backend.modules.live_room.schemas import RoomCreate, RoomUpdate, RoomOut, ScheduleIn, ScheduleOut

router = APIRouter(prefix="/api/live-rooms", tags=["live_rooms"])


@router.get("", response_model=list[RoomOut])
async def list_rooms(db: AsyncSession = Depends(get_db)):
    return await service.list_rooms(db)


@router.get("/{room_id}", response_model=RoomOut)
async def get_room(room_id: str, db: AsyncSession = Depends(get_db)):
    r = await service.get_room(db, room_id)
    if not r:
        raise HTTPException(404, "Room not found")
    return r


@router.post("", response_model=RoomOut, status_code=201)
async def create_room(data: RoomCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_room(db, data)


@router.put("/{room_id}", response_model=RoomOut)
async def update_room(room_id: str, data: RoomUpdate, db: AsyncSession = Depends(get_db)):
    r = await service.update_room(db, room_id, data)
    if not r:
        raise HTTPException(404, "Room not found")
    return r


@router.delete("/{room_id}", status_code=204)
async def delete_room(room_id: str, db: AsyncSession = Depends(get_db)):
    ok = await service.delete_room(db, room_id)
    if not ok:
        raise HTTPException(400, "Cannot delete room (not found or currently live)")


@router.post("/{room_id}/attach/{live_video_id}", response_model=RoomOut)
async def attach_video(room_id: str, live_video_id: str, db: AsyncSession = Depends(get_db)):
    r = await service.attach_video(db, room_id, live_video_id)
    if not r:
        raise HTTPException(404, "Room or live video not found")
    return r


@router.post("/{room_id}/start", response_model=RoomOut)
async def start_room(room_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await service.start_room(db, room_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{room_id}/stop", response_model=RoomOut)
async def stop_room(room_id: str, db: AsyncSession = Depends(get_db)):
    r = await service.stop_room(db, room_id)
    if not r:
        raise HTTPException(400, "Room is not live")
    return r


# ---- 排班 ----
@router.get("/{room_id}/schedule", response_model=ScheduleOut | None)
async def get_schedule(room_id: str, db: AsyncSession = Depends(get_db)):
    return await service.get_schedule(db, room_id)


@router.put("/{room_id}/schedule", response_model=ScheduleOut)
async def set_schedule(room_id: str, data: ScheduleIn, db: AsyncSession = Depends(get_db)):
    return await service.set_schedule(db, room_id, data)
