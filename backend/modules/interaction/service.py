from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.interaction import InteractionConfig, ReplyTemplate
from backend.modules.interaction.schemas import InteractionConfigUpdate, ReplyTemplateCreate


async def get_config(db: AsyncSession) -> InteractionConfig:
    result = await db.execute(select(InteractionConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        config = InteractionConfig()
        db.add(config)
        await db.commit()
        await db.refresh(config)
    return config


async def update_config(db: AsyncSession, data: InteractionConfigUpdate) -> InteractionConfig:
    config = await get_config(db)
    if data.reply_mode is not None:
        config.reply_mode = data.reply_mode
    if data.reply_decision is not None:
        config.reply_decision = data.reply_decision
    if data.reply_style is not None:
        config.reply_style = data.reply_style
    if data.tts_speed is not None:
        config.tts_speed = data.tts_speed
    if data.tts_volume is not None:
        config.tts_volume = data.tts_volume
    if data.tts_pitch is not None:
        config.tts_pitch = data.tts_pitch
    await db.commit()
    await db.refresh(config)
    return config


async def list_templates(db: AsyncSession) -> list[ReplyTemplate]:
    result = await db.execute(select(ReplyTemplate).order_by(ReplyTemplate.created_at.desc()))
    return list(result.scalars().all())


async def create_template(db: AsyncSession, data: ReplyTemplateCreate) -> ReplyTemplate:
    tmpl = ReplyTemplate(
        product_id=data.product_id,
        keywords=data.keywords,
        reply_text=data.reply_text,
        reply_type=data.reply_type,
    )
    db.add(tmpl)
    await db.commit()
    await db.refresh(tmpl)
    return tmpl


async def delete_template(db: AsyncSession, template_id: str) -> bool:
    tmpl = await db.get(ReplyTemplate, template_id)
    if not tmpl:
        return False
    await db.delete(tmpl)
    await db.commit()
    return True
