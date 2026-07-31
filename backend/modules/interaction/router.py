from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import get_db
from backend.modules.interaction import service
from backend.modules.interaction.schemas import (
    InteractionConfigOut, InteractionConfigUpdate,
    ReplyTemplateCreate, ReplyTemplateOut,
)

router = APIRouter(prefix="/api/interaction", tags=["interaction"])


@router.get("/config", response_model=InteractionConfigOut)
async def get_config(db: AsyncSession = Depends(get_db)):
    return await service.get_config(db)


@router.put("/config", response_model=InteractionConfigOut)
async def update_config(data: InteractionConfigUpdate, db: AsyncSession = Depends(get_db)):
    return await service.update_config(db, data)


@router.get("/templates", response_model=list[ReplyTemplateOut])
async def list_templates(db: AsyncSession = Depends(get_db)):
    return await service.list_templates(db)


@router.post("/templates", response_model=ReplyTemplateOut, status_code=201)
async def create_template(data: ReplyTemplateCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_template(db, data)


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(template_id: str, db: AsyncSession = Depends(get_db)):
    ok = await service.delete_template(db, template_id)
    if not ok:
        raise HTTPException(404, "Template not found")
