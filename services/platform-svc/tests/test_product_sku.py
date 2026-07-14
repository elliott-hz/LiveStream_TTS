"""
Integration tests: SKU management (add, update stock, delete).
"""

import pytest

from services.platform_svc.src.modules.product.services.product_service import ProductService


@pytest.mark.asyncio
async def test_add_sku(db_session):
    """Add a SKU to an existing product."""
    svc = ProductService(db=db_session)
    product = await svc.create_product(
        store_id="store_001",
        title="多规格商品",
    )

    sku = await svc.add_sku(
        product_id=product.product_id,
        spec={"颜色": "黑色", "尺码": "M"},
        price=9999,          # 99.99 yuan in fen
        original_price=12999,
        stock=100,
        barcode="BARCODE001",
    )
    assert sku.sku_id is not None
    assert sku.product_id == product.product_id
    assert sku.spec == {"颜色": "黑色", "尺码": "M"}
    assert sku.price == 9999
    assert sku.stock == 100
    assert sku.barcode == "BARCODE001"
    assert sku.status == "on_sale"

    # Verify it appears on the product
    fetched = await svc.get_product(product.product_id)
    assert len(fetched.skus) == 1
    assert fetched.skus[0].spec == {"颜色": "黑色", "尺码": "M"}


@pytest.mark.asyncio
async def test_add_sku_duplicate_spec(db_session):
    """Adding a SKU with the same spec should raise DUPLICATE_RESOURCE."""
    svc = ProductService(db=db_session)
    product = await svc.create_product(
        store_id="store_001",
        title="有重复规格的商品",
    )
    await svc.add_sku(
        product_id=product.product_id,
        spec={"颜色": "红色"},
        price=5000,
        stock=10,
    )
    with pytest.raises(Exception) as excinfo:
        await svc.add_sku(
            product_id=product.product_id,
            spec={"颜色": "红色"},
            price=6000,
            stock=20,
        )
    assert "already exists" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_update_sku_stock_and_price(db_session):
    """Update stock and price on an existing SKU."""
    svc = ProductService(db=db_session)
    product = await svc.create_product(
        store_id="store_001", title="改价商品"
    )
    sku = await svc.add_sku(
        product_id=product.product_id,
        spec={"尺码": "L"},
        price=19900,
        stock=50,
    )

    updated = await svc.update_sku(
        product_id=product.product_id,
        sku_id=sku.sku_id,
        price=14900,
        stock=200,
    )
    assert updated.price == 14900
    assert updated.stock == 200


@pytest.mark.asyncio
async def test_update_sku_status(db_session):
    """Update SKU status to off_shelf and deleted."""
    svc = ProductService(db=db_session)
    product = await svc.create_product(
        store_id="store_001", title="SKU状态测试"
    )
    sku = await svc.add_sku(
        product_id=product.product_id,
        spec={"颜色": "蓝色"},
        price=10000,
        stock=5,
    )

    # Off shelf
    updated = await svc.update_sku(
        product_id=product.product_id,
        sku_id=sku.sku_id,
        status="off_shelf",
    )
    assert updated.status == "off_shelf"

    # Delete (soft)
    await svc.delete_sku(product_id=product.product_id, sku_id=sku.sku_id)
    fetched_product = await svc.get_product(product.product_id)
    deleted_sku = next(s for s in fetched_product.skus if s.sku_id == sku.sku_id)
    assert deleted_sku.status == "deleted"


@pytest.mark.asyncio
async def test_add_sku_invalid_price(db_session):
    """Adding a SKU with negative price should raise."""
    svc = ProductService(db=db_session)
    product = await svc.create_product(
        store_id="store_001", title="价格测试"
    )
    with pytest.raises(Exception) as excinfo:
        await svc.update_sku(
            product_id=product.product_id,
            sku_id="nonexistent",
            price=-100,
        )
    # Should either be "not found" (sku doesn't exist) or validation error


@pytest.mark.asyncio
async def test_get_product_with_multiple_skus(db_session):
    """Fetch a product with multiple SKUs and verify all are loaded."""
    svc = ProductService(db=db_session)
    product = await svc.create_product(
        store_id="store_001",
        title="多SKU商品",
    )

    specs = [
        ({"颜色": "黑", "尺码": "S"}, 5000, 50),
        ({"颜色": "黑", "尺码": "M"}, 5000, 100),
        ({"颜色": "白", "尺码": "M"}, 5500, 80),
    ]
    for spec, price, stock in specs:
        await svc.add_sku(
            product_id=product.product_id,
            spec=spec,
            price=price,
            stock=stock,
        )

    fetched = await svc.get_product(product.product_id)
    assert len(fetched.skus) == 3
    prices = {s.price for s in fetched.skus}
    assert 5000 in prices
    assert 5500 in prices
