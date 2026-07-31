import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.system import PlatformConfig
from backend.modules.platform.schemas import PlatformConfigUpdate, PlatformCapabilityInfo

# 各平台能力矩阵
PLATFORM_CAPABILITIES = {
    "taobao":   {"stream": True, "danmaku": True,  "product_pop": True,  "reply": True},
    "douyin":   {"stream": True, "danmaku": True,  "product_pop": True,  "reply": False},
    "kuaishou": {"stream": True, "danmaku": True,  "product_pop": False, "reply": False},
    "jd":       {"stream": True, "danmaku": False, "product_pop": False, "reply": False},
    "pdd":      {"stream": True, "danmaku": False, "product_pop": False, "reply": False},
}

PLATFORM_NAMES = {"taobao": "淘宝", "douyin": "抖音", "kuaishou": "快手", "jd": "京东", "pdd": "拼多多"}
PLATFORM_ICONS = {"taobao": "🟠", "douyin": "🎵", "kuaishou": "📺", "jd": "🐶", "pdd": "📱"}


async def list_configs(db: AsyncSession) -> list[PlatformConfig]:
    result = await db.execute(select(PlatformConfig).order_by(PlatformConfig.platform))
    return list(result.scalars().all())


async def get_config(db: AsyncSession, platform: str) -> PlatformConfig | None:
    result = await db.execute(
        select(PlatformConfig).where(PlatformConfig.platform == platform)
    )
    return result.scalar_one_or_none()


async def upsert_config(db: AsyncSession, platform: str, data: PlatformConfigUpdate) -> PlatformConfig:
    cfg = await get_config(db, platform)
    if not cfg:
        cfg = PlatformConfig(platform=platform)
        db.add(cfg)
    if data.app_key is not None:
        cfg.app_key = data.app_key
    if data.app_secret is not None:
        cfg.app_secret = data.app_secret
    if data.rtmp_template is not None:
        cfg.rtmp_template = data.rtmp_template
    cfg.is_active = bool(cfg.app_key and cfg.app_secret)
    await db.commit()
    await db.refresh(cfg)
    return cfg


async def delete_config(db: AsyncSession, platform: str) -> bool:
    cfg = await get_config(db, platform)
    if not cfg:
        return False
    await db.delete(cfg)
    await db.commit()
    return True


async def get_capabilities(db: AsyncSession) -> list[PlatformCapabilityInfo]:
    """获取所有平台的能力矩阵 + 接入状态"""
    configs = await list_configs(db)
    connected = {c.platform: c for c in configs}

    result = []
    for platform in ["taobao", "douyin", "kuaishou", "jd", "pdd"]:
        caps = PLATFORM_CAPABILITIES.get(platform, {})
        cfg = connected.get(platform)
        result.append(PlatformCapabilityInfo(
            platform=platform,
            name=PLATFORM_NAMES.get(platform, platform),
            icon=PLATFORM_ICONS.get(platform, ""),
            is_connected=cfg.is_active if cfg else False,
            capabilities=caps,
        ))
    return result
