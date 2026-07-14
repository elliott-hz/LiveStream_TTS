"""
Integration tests: Product CRUD (create -> get -> update -> list -> delete).
"""

import pytest

from libs.testing import fake_product
from services.product_service import ProductService


@pytest.mark.asyncio
async def test_create_product(db_session):
    """Create a product and verify it's persisted."""
    svc = ProductService(db=db_session)
    product = await svc.create_product(
        store_id="store_001",
        title="测试商品A",
        subtitle="副标题",
        description="这是一个测试商品",
        category_path=["女装", "连衣裙"],
        brand="TestBrand",
        attributes={"材质": "棉"},
        selling_points=["舒适", "时尚"],
    )
    assert product.product_id is not None
    assert product.title == "测试商品A"
    assert product.store_id == "store_001"
    assert product.status == "draft"
    assert product.category_path == ["女装", "连衣裙"]
    assert product.attributes == {"材质": "棉"}
    assert product.selling_points == ["舒适", "时尚"]
    assert product.created_at is not None
    assert product.updated_at is not None


@pytest.mark.asyncio
async def test_get_product(db_session):
    """Create and then fetch a product by ID."""
    svc = ProductService(db=db_session)
    created = await svc.create_product(
        store_id="store_001",
        title="可查询的商品",
    )
    fetched = await svc.get_product(created.product_id)
    assert fetched.product_id == created.product_id
    assert fetched.title == "可查询的商品"


@pytest.mark.asyncio
async def test_get_product_not_found(db_session):
    """Fetching a non-existent product should raise AppError."""
    svc = ProductService(db=db_session)
    with pytest.raises(Exception) as excinfo:
        await svc.get_product("non_existent_id")
    assert "not found" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_update_product(db_session):
    """Update title, subtitle, and status of a product."""
    svc = ProductService(db=db_session)
    product = await svc.create_product(
        store_id="store_001", title="原标题"
    )
    updated = await svc.update_product(
        product_id=product.product_id,
        title="新标题",
        subtitle="新副标题",
        status="published",
    )
    assert updated.title == "新标题"
    assert updated.subtitle == "新副标题"
    assert updated.status == "published"


@pytest.mark.asyncio
async def test_list_products(db_session):
    """List products with pagination and filters."""
    svc = ProductService(db=db_session)
    for i in range(5):
        await svc.create_product(
            store_id="store_001",
            title=f"商品{i}",
            category_path=["电子"] if i % 2 == 0 else ["服装"],
        )

    # All products
    products, total = await svc.list_products(store_id="store_001")
    assert total == 5
    assert len(products) == 5

    # With search
    products, total = await svc.list_products(
        store_id="store_001", search_query="商品1"
    )
    assert total == 1

    # Pagination
    products, total = await svc.list_products(
        store_id="store_001", page=1, page_size=2
    )
    assert len(products) == 2
    assert total == 5

    # With status filter
    products, total = await svc.list_products(
        store_id="store_001", status="draft"
    )
    assert total == 5


@pytest.mark.asyncio
async def test_delete_product(db_session):
    """Delete a product and verify it's gone."""
    svc = ProductService(db=db_session)
    product = await svc.create_product(
        store_id="store_001", title="待删除商品"
    )
    await svc.delete_product(product.product_id)

    with pytest.raises(Exception) as excinfo:
        await svc.get_product(product.product_id)
    assert "not found" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_create_product_with_images(db_session):
    """Create a product with images attached."""
    svc = ProductService(db=db_session)
    images = [
        {
            "url": "https://example.com/main.jpg",
            "type": "main",
            "width": 800,
            "height": 800,
            "sort_order": 0,
        },
        {
            "url": "https://example.com/detail1.jpg",
            "type": "detail",
            "width": 1600,
            "height": 1200,
            "sort_order": 1,
        },
    ]
    product = await svc.create_product(
        store_id="store_001",
        title="带图片的商品",
        images=images,
    )
    assert len(product.images) == 2
    assert product.images[0].url == "https://example.com/main.jpg"


@pytest.mark.asyncio
async def test_create_product_invalid(db_session):
    """Creating a product without required fields should raise."""
    svc = ProductService(db=db_session)
    with pytest.raises(Exception) as excinfo:
        await svc.create_product(store_id="", title="")
    assert "store_id" in str(excinfo.value).lower() or "title" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_create_product_via_fake_helper(db_session):
    """Use the shared fake_product() helper to seed test data."""
    svc = ProductService(db=db_session)
    data = fake_product(store_id="store_002", title="来自helper的商品")
    product = await svc.create_product(
        store_id=data["store_id"],
        title=data["title"],
        category_path=data["category_path"],
        attributes=data["attributes"],
        selling_points=data["selling_points"],
    )
    assert product.title == "来自helper的商品"
    assert product.store_id == "store_002"
    assert product.selling_points == ["卖点1", "卖点2"]
