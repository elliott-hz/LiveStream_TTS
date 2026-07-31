from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import get_db
from backend.modules.account import service
from backend.modules.account.schemas import MerchantOut, MerchantUpdate, UserOut, UserCreate

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/merchant", response_model=MerchantOut)
async def get_merchant(db: AsyncSession = Depends(get_db)):
    return await service.get_merchant(db)


@router.put("/merchant", response_model=MerchantOut)
async def update_merchant(data: MerchantUpdate, db: AsyncSession = Depends(get_db)):
    return await service.update_merchant(db, data)


@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    return await service.list_users(db)


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_user(db, data)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)):
    ok = await service.delete_user(db, user_id)
    if not ok:
        raise HTTPException(404, "User not found")
