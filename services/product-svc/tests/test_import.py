"""
Integration tests: CSV import of products.
"""

import pytest

from services.product_service import ProductService


@pytest.mark.asyncio
async def test_import_products_csv(db_session):
    """Import valid CSV content and verify products are created."""
    csv_content = (
        "title,subtitle,description,category_path,brand,price,original_price,stock,barcode\n"
        "商品A,副标题A,描述A,女装/连衣裙,品牌A,9900,12900,100,BAR001\n"
        "商品B,副标题B,描述B,男装/上衣,品牌B,19900,25900,50,BAR002\n"
        "商品C,,,食品/零食,品牌C,1500,2000,500,BAR003\n"
    )
    svc = ProductService(db=db_session)
    result = await svc.import_products(
        store_id="store_001",
        csv_content=csv_content,
    )
    assert result["total"] == 3
    assert result["success"] == 3
    assert result["failed"] == 0
    assert len(result["errors"]) == 0

    # Verify products in DB
    products, total = await svc.list_products(store_id="store_001")
    assert total == 3

    titles = {p.title for p in products}
    assert "商品A" in titles
    assert "商品B" in titles
    assert "商品C" in titles


@pytest.mark.asyncio
async def test_import_products_with_errors(db_session):
    """Import CSV with some invalid rows; partial success."""
    csv_content = (
        "title,price,stock\n"
        "好商品,9900,100\n"
        ",5000,50\n"          # missing title → error
        "另一个好商品,abc,10\n"  # invalid price → defaults to 0 (not an error per se)
    )
    svc = ProductService(db=db_session)
    result = await svc.import_products(
        store_id="store_001",
        csv_content=csv_content,
    )
    # Row 2 (missing title) fails; row 3 (bad price) succeeds with defaults
    assert result["total"] == 3
    assert result["success"] >= 2
    assert result["failed"] >= 1
    assert any("title" in err.lower() for err in result["errors"])


@pytest.mark.asyncio
async def test_import_empty_csv(db_session):
    """Empty CSV content should raise an error."""
    svc = ProductService(db=db_session)
    with pytest.raises(Exception) as excinfo:
        await svc.import_products(store_id="store_001", csv_content="")
    assert "csv_content" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_import_products_large_batch(db_session):
    """Import a larger batch and verify counts."""
    rows = ["title,price,stock"]
    for i in range(50):
        rows.append(f"批量商品{i},{i * 100},{i * 10}")

    svc = ProductService(db=db_session)
    result = await svc.import_products(
        store_id="store_002",
        csv_content="\n".join(rows),
    )
    assert result["total"] == 50
    assert result["success"] == 50
    assert result["failed"] == 0
