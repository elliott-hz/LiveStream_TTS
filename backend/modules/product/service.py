import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.product import Product, ProductKB
from backend.modules.product.schemas import ProductCreate, ProductUpdate, ProductImportRequest


async def list_products(db: AsyncSession) -> list[Product]:
    result = await db.execute(
        select(Product).options(selectinload(Product.platform_kbs)).order_by(Product.created_at.desc())
    )
    return list(result.scalars().all())


async def get_product(db: AsyncSession, product_id: str) -> Product | None:
    result = await db.execute(
        select(Product).options(selectinload(Product.platform_kbs)).where(Product.id == product_id)
    )
    return result.scalar_one_or_none()


async def create_product(db: AsyncSession, data: ProductCreate) -> Product:
    product = Product(name=data.name, sku=data.sku, category=data.category)
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def update_product(db: AsyncSession, product_id: str, data: ProductUpdate) -> Product | None:
    product = await get_product(db, product_id)
    if not product:
        return None
    if data.name is not None:
        product.name = data.name
    if data.sku is not None:
        product.sku = data.sku
    if data.category is not None:
        product.category = data.category
    await db.commit()
    await db.refresh(product)
    return product


async def delete_product(db: AsyncSession, product_id: str) -> bool:
    product = await get_product(db, product_id)
    if not product:
        return False
    await db.delete(product)
    await db.commit()
    return True


async def import_product(db: AsyncSession, data: ProductImportRequest) -> Product:
    """AI 导入：从平台链接抓取商品详情并存入知识库"""
    # 1. 模拟抓取平台商品详情 (PoC 阶段用占位数据)
    kb_data = await _fetch_product_detail(data.platform, data.url)

    # 2. 找到或创建商品
    if data.product_id:
        product = await get_product(db, data.product_id)
        if not product:
            raise ValueError(f"Product {data.product_id} not found")
    else:
        product = Product(
            name=kb_data["name"],
            sku=kb_data.get("sku", ""),
            category=kb_data.get("category", ""),
        )
        db.add(product)
        await db.flush()

    # 3. 添加/更新平台知识库
    kb = ProductKB(
        product_id=product.id,
        platform=data.platform,
        platform_name=kb_data["platform_name"],
        platform_sku=kb_data.get("platform_sku", ""),
        price=kb_data.get("price", ""),
        detail_html=kb_data.get("detail_html", ""),
    )
    db.add(kb)
    await db.commit()
    await db.refresh(product)
    return product


async def _fetch_product_detail(platform: str, url: str) -> dict:
    """PoC: 模拟抓取。实际实现时对接各平台开放 API 或爬虫。"""
    # TODO: 实际抓取逻辑
    return {
        "name": f"导入商品 ({platform})",
        "sku": "",
        "category": "",
        "platform_name": f"平台商品名 ({platform})",
        "platform_sku": "",
        "price": "",
        "detail_html": f"<p>从 {url} 导入的商品详情</p>",
    }
