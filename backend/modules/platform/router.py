from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import get_db
from backend.modules.platform import service
from backend.modules.platform.schemas import PlatformConfigOut, PlatformConfigUpdate, PlatformCapabilityInfo

router = APIRouter(prefix="/api/platform", tags=["platform"])


@router.get("/capabilities", response_model=list[PlatformCapabilityInfo])
async def get_capabilities(db: AsyncSession = Depends(get_db)):
    """获取所有平台的能力矩阵 + 接入状态"""
    return await service.get_capabilities(db)


@router.get("/configs", response_model=list[PlatformConfigOut])
async def list_configs(db: AsyncSession = Depends(get_db)):
    return await service.list_configs(db)


@router.put("/configs/{platform}", response_model=PlatformConfigOut)
async def upsert_config(platform: str, data: PlatformConfigUpdate, db: AsyncSession = Depends(get_db)):
    return await service.upsert_config(db, platform, data)


@router.delete("/configs/{platform}", status_code=204)
async def delete_config(platform: str, db: AsyncSession = Depends(get_db)):
    ok = await service.delete_config(db, platform)
    if not ok:
        raise HTTPException(404, "Platform config not found")
