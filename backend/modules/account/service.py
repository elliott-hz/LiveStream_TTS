from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.account import Merchant, User
from backend.modules.account.schemas import MerchantUpdate, UserCreate


# ---- Merchant ----

async def get_merchant(db: AsyncSession) -> Merchant | None:
    """获取商户信息（当前单商户模式）"""
    result = await db.execute(select(Merchant).limit(1))
    merchant = result.scalar_one_or_none()
    if not merchant:
        # 自动创建默认商户
        merchant = Merchant(
            name="张老板的店铺",
            tier="pro",
            subscribed_until=datetime(2027, 1, 24),
            max_rooms=10,
            max_streams=5,
        )
        db.add(merchant)
        await db.commit()
        await db.refresh(merchant)
    return merchant


async def update_merchant(db: AsyncSession, data: MerchantUpdate) -> Merchant:
    merchant = await get_merchant(db)
    if data.name is not None:
        merchant.name = data.name
    if data.tier is not None:
        merchant.tier = data.tier
    await db.commit()
    await db.refresh(merchant)
    return merchant


# ---- Users ----

async def list_users(db: AsyncSession) -> list[User]:
    merchant = await get_merchant(db)
    result = await db.execute(
        select(User).where(User.merchant_id == merchant.id).order_by(User.username)
    )
    return list(result.scalars().all())


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    merchant = await get_merchant(db)
    user = User(
        merchant_id=merchant.id,
        username=data.username,
        role=data.role,
        quota_hours=data.quota_hours,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: str) -> bool:
    user = await db.get(User, user_id)
    if not user:
        return False
    await db.delete(user)
    await db.commit()
    return True
