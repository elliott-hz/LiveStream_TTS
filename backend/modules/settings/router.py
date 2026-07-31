from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import get_db
from backend.modules.settings import service
from backend.modules.settings.schemas import SettingOut, SettingUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=list[SettingOut])
async def get_all(db: AsyncSession = Depends(get_db)):
    return await service.get_all(db)


@router.put("/{key}", response_model=SettingOut)
async def update_setting(key: str, data: SettingUpdate, db: AsyncSession = Depends(get_db)):
    s = await service.update(db, key, data)
    if not s:
        raise HTTPException(404, "Setting not found")
    return s
