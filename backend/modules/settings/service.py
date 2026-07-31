from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.system import SystemSetting
from backend.modules.settings.schemas import SettingUpdate

DEFAULTS = {
    "bgm_volume":      ("30",    "默认 BGM 音量 (0-100)"),
    "auto_reply":       ("true",  "是否默认开启自动回复"),
    "tts_enabled":      ("true",  "是否默认开启 TTS 语音"),
    "language":         ("zh",    "界面语言"),
}


async def get_all(db: AsyncSession) -> list[SystemSetting]:
    result = await db.execute(select(SystemSetting))
    existing = {s.key: s for s in result.scalars().all()}

    # 补全缺失的默认值
    for key, (val, desc) in DEFAULTS.items():
        if key not in existing:
            s = SystemSetting(key=key, value=val, description=desc)
            db.add(s)
            existing[key] = s

    await db.commit()
    return list(existing.values())


async def get(db: AsyncSession, key: str) -> SystemSetting | None:
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    return result.scalar_one_or_none()


async def update(db: AsyncSession, key: str, data: SettingUpdate) -> SystemSetting | None:
    s = await get(db, key)
    if not s:
        # create if not exists
        s = SystemSetting(key=key, value=data.value, description="")
        db.add(s)
    else:
        s.value = data.value
    await db.commit()
    await db.refresh(s)
    return s
