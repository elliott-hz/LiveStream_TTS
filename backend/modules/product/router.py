from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import get_db
from backend.modules.product import service
from backend.modules.product.schemas import (
    ProductCreate,
    ProductUpdate,
    ProductOut,
    ProductImportRequest,
)

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
async def list_products(db: AsyncSession = Depends(get_db)):
    return await service.list_products(db)


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    p = await service.get_product(db, product_id)
    if not p:
        raise HTTPException(404, "Product not found")
    return p


@router.post("", response_model=ProductOut, status_code=201)
async def create_product(data: ProductCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_product(db, data)


@router.put("/{product_id}", response_model=ProductOut)
async def update_product(product_id: str, data: ProductUpdate, db: AsyncSession = Depends(get_db)):
    p = await service.update_product(db, product_id, data)
    if not p:
        raise HTTPException(404, "Product not found")
    return p


@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: str, db: AsyncSession = Depends(get_db)):
    ok = await service.delete_product(db, product_id)
    if not ok:
        raise HTTPException(404, "Product not found")


@router.post("/import", response_model=ProductOut, status_code=201)
async def import_product(data: ProductImportRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await service.import_product(db, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
