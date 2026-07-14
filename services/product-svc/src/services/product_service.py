"""
ProductService — business logic for all 16 product-related RPCs.

Every public method corresponds to one RPC.  Methods raise AppError
(defined in libs.common.errors) on failure; the gRPC layer catches
them and translates to proto Error responses.
"""

import csv
import io
from datetime import datetime
from typing import Any

from sqlalchemy import select, func, cast, String, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from libs.common.errors import (
    AppError,
    ErrorCode,
    not_found,
    invalid_arg,
)
from libs.common.logging import get_logger

from models.product import (
    Product,
    Sku,
    ProductImage,
    ProductVideo,
    Category,
)

logger = get_logger(__name__)

# ── Constants ──

VALID_PRODUCT_STATUSES = {"draft", "published", "archived"}
VALID_SKU_STATUSES = {"on_sale", "off_shelf", "deleted"}
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


# ── Relationship loading options ──

_PRODUCT_LOAD_OPTS = (
    selectinload(Product.skus),
    selectinload(Product.images),
    selectinload(Product.videos),
)


def _now_ms() -> int:
    """Return current Unix timestamp in milliseconds."""
    return int(datetime.utcnow().timestamp() * 1000)


def _refresh_opts() -> list[str]:
    """Return attribute names to refresh for eager-loading product relationships."""
    return ["skus", "images", "videos"]


# ── Service ──


class ProductService:
    """Product business logic — injected with a DB session."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ──────────────────────────────────────────────────────────
    #  Product CRUD
    # ──────────────────────────────────────────────────────────

    async def create_product(
        self,
        store_id: str,
        title: str,
        subtitle: str | None = None,
        description: str | None = None,
        category_path: list[str] | None = None,
        brand: str | None = None,
        images: list[dict[str, Any]] | None = None,
        attributes: dict[str, str] | None = None,
        selling_points: list[str] | None = None,
        created_by: str | None = None,
    ) -> Product:
        """Create a new product in draft status."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")
        if not title or not title.strip():
            raise invalid_arg("title", "must not be empty")

        product = Product(
            store_id=store_id,
            title=title.strip(),
            subtitle=subtitle.strip() if subtitle else None,
            description=description,
            category_path=category_path or [],
            brand=brand,
            attributes=attributes or {},
            selling_points=selling_points or [],
            status="draft",
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(product)
        await self.db.flush()

        if images:
            for img_data in images:
                img = ProductImage(
                    product_id=product.product_id,
                    url=img_data.get("url", ""),
                    type=img_data.get("type", "main"),
                    width=img_data.get("width"),
                    height=img_data.get("height"),
                    sort_order=img_data.get("sort_order", 0),
                )
                self.db.add(img)
            await self.db.flush()

        # Refresh to eagerly load relationships
        await self.db.refresh(product, _refresh_opts())
        logger.info("product.created", product_id=product.product_id, store_id=store_id)
        return product

    async def get_product(self, product_id: str) -> Product:
        """Fetch a single product with SKUs, images, and videos eagerly loaded."""
        if not product_id:
            raise invalid_arg("product_id", "must not be empty")

        stmt = (
            select(Product)
            .options(*_PRODUCT_LOAD_OPTS)
            .where(Product.product_id == product_id)
            .execution_options(populate_existing=True)
        )
        result = await self.db.execute(stmt)
        product = result.scalars().one_or_none()
        if not product:
            raise not_found("Product", product_id)
        return product

    async def update_product(
        self,
        product_id: str,
        title: str | None = None,
        subtitle: str | None = None,
        description: str | None = None,
        status: str | None = None,
        updated_by: str | None = None,
    ) -> Product:
        """Partially update a product's scalar fields."""
        product = await self.get_product(product_id)

        if title is not None:
            if not title.strip():
                raise invalid_arg("title", "must not be empty")
            product.title = title.strip()
        if subtitle is not None:
            product.subtitle = subtitle.strip() if subtitle else None
        if description is not None:
            product.description = description
        if status is not None:
            if status not in VALID_PRODUCT_STATUSES:
                raise invalid_arg("status", f"must be one of {VALID_PRODUCT_STATUSES}")
            product.status = status
        if updated_by is not None:
            product.updated_by = updated_by

        product.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(product, _refresh_opts())
        logger.info("product.updated", product_id=product_id)
        return product

    async def delete_product(self, product_id: str) -> None:
        """Hard-delete a product (and cascaded SKUs/images/videos)."""
        product = await self.get_product(product_id)
        await self.db.delete(product)
        await self.db.flush()
        logger.info("product.deleted", product_id=product_id)

    async def list_products(
        self,
        store_id: str,
        category: str | None = None,
        status: str | None = None,
        search_query: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[Product], int]:
        """Paginated product listing with optional filters.

        Supported filters:
            category  — substring match on JSON category_path text representation
            status    — exact match on product status
            search    — LIKE match against title, subtitle, description, brand

        Returns:
            (products_list, total_count)
        """
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")

        page = max(page, 1)
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

        conditions = [Product.store_id == store_id]

        if category:
            # Cross-DB: cast JSON to text and use LIKE-based contains
            conditions.append(
                cast(Product.category_path, String).contains(category)
            )

        if status:
            if status not in VALID_PRODUCT_STATUSES:
                raise invalid_arg("status", f"must be one of {VALID_PRODUCT_STATUSES}")
            conditions.append(Product.status == status)

        if search_query:
            like_pattern = f"%{search_query}%"
            conditions.append(
                or_(
                    Product.title.ilike(like_pattern),
                    Product.subtitle.ilike(like_pattern),
                    Product.description.ilike(like_pattern),
                    Product.brand.ilike(like_pattern),
                )
            )

        # Count
        count_stmt = select(func.count()).select_from(Product).where(*conditions)
        total_result = await self.db.execute(count_stmt)
        total_count: int = total_result.scalar() or 0

        # Fetch page
        offset = (page - 1) * page_size
        stmt = (
            select(Product)
            .options(*_PRODUCT_LOAD_OPTS)
            .where(*conditions)
            .order_by(Product.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        products = list(result.scalars().all())

        return products, total_count

    # ──────────────────────────────────────────────────────────
    #  SKU Management
    # ──────────────────────────────────────────────────────────

    async def add_sku(
        self,
        product_id: str,
        spec: dict[str, str] | None = None,
        price: int = 0,
        original_price: int = 0,
        stock: int = 0,
        barcode: str | None = None,
    ) -> Sku:
        """Add a new SKU to an existing product.

        Raises DUPLICATE_RESOURCE if a SKU with identical non-deleted
        specs already exists.
        """
        product = await self.get_product(product_id)

        spec = spec or {}
        for existing in product.skus:
            if existing.status != "deleted" and existing.spec == spec:
                raise AppError(
                    ErrorCode.DUPLICATE_RESOURCE,
                    f"SKU with spec {spec!r} already exists for product {product_id}",
                )

        sku = Sku(
            product_id=product_id,
            spec=spec,
            price=price,
            original_price=original_price,
            stock=stock,
            barcode=barcode,
            status="on_sale",
        )
        self.db.add(sku)
        await self.db.flush()

        # Refresh the product's SKU list so the identity map is up to date
        await self.db.refresh(product, ["skus"])

        logger.info("sku.created", sku_id=sku.sku_id, product_id=product_id, price=price)
        return sku

    async def update_sku(
        self,
        product_id: str,
        sku_id: str,
        price: int | None = None,
        stock: int | None = None,
        status: str | None = None,
    ) -> Sku:
        """Partially update a SKU's price, stock, and/or status."""
        await self.get_product(product_id)  # verify product exists

        stmt = select(Sku).where(Sku.sku_id == sku_id, Sku.product_id == product_id)
        result = await self.db.execute(stmt)
        sku = result.scalars().one_or_none()
        if not sku:
            raise not_found("Sku", sku_id)

        if price is not None:
            if price < 0:
                raise invalid_arg("price", "must be >= 0")
            sku.price = price
        if stock is not None:
            if stock < 0:
                raise invalid_arg("stock", "must be >= 0")
            sku.stock = stock
        if status is not None:
            if status not in VALID_SKU_STATUSES:
                raise invalid_arg("status", f"must be one of {VALID_SKU_STATUSES}")
            sku.status = status

        await self.db.flush()
        logger.info("sku.updated", sku_id=sku_id, product_id=product_id)
        return sku

    async def delete_sku(self, product_id: str, sku_id: str) -> None:
        """Soft-delete a SKU (status = 'deleted') to preserve order history."""
        product = await self.get_product(product_id)
        sku = await self._get_sku(product_id, sku_id)
        sku.status = "deleted"
        await self.db.flush()
        await self.db.refresh(product, ["skus"])
        logger.info("sku.deleted", sku_id=sku_id, product_id=product_id)

    async def _get_sku(self, product_id: str, sku_id: str) -> Sku:
        """Internal: fetch a single SKU by ID, verifying product ownership."""
        stmt = select(Sku).where(Sku.sku_id == sku_id, Sku.product_id == product_id)
        result = await self.db.execute(stmt)
        sku = result.scalars().one_or_none()
        if not sku:
            raise not_found("Sku", sku_id)
        return sku

    # ──────────────────────────────────────────────────────────
    #  Category
    # ──────────────────────────────────────────────────────────

    async def list_categories(self, store_id: str) -> list[Category]:
        """Return all categories for a store, ordered by level and name."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")
        stmt = (
            select(Category)
            .where(Category.store_id == store_id)
            .order_by(Category.level, Category.name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ──────────────────────────────────────────────────────────
    #  Import / Export
    # ──────────────────────────────────────────────────────────

    async def import_products(
        self,
        store_id: str,
        csv_content: str,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Bulk-import products from CSV text.

        Expected CSV columns (header row):
            title, subtitle, description, category_path, brand,
            price, original_price, stock, barcode

        category_path is treated as a "/"-separated string.

        Returns a summary dict with ``total``, ``success``, ``failed``,
        and ``errors`` (list of per-row error strings).
        """
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")
        if not csv_content:
            raise invalid_arg("csv_content", "must not be empty")

        reader = csv.DictReader(io.StringIO(csv_content))
        total = 0
        success = 0
        failed = 0
        errors: list[str] = []

        for row_num, row in enumerate(reader, start=2):
            total += 1
            try:
                title = row.get("title", "").strip()
                if not title:
                    raise ValueError("title is required")

                product = Product(
                    store_id=store_id,
                    title=title,
                    subtitle=row.get("subtitle", "").strip() or None,
                    description=row.get("description", "").strip() or None,
                    category_path=(
                        [c.strip() for c in row.get("category_path", "").split("/") if c.strip()]
                        if row.get("category_path")
                        else []
                    ),
                    brand=row.get("brand", "").strip() or None,
                    status="draft",
                    created_by=created_by,
                    updated_by=created_by,
                )
                self.db.add(product)
                await self.db.flush()

                sku = Sku(
                    product_id=product.product_id,
                    spec={},
                    price=_parse_int(row.get("price"), 0),
                    original_price=_parse_int(row.get("original_price"), 0),
                    stock=_parse_int(row.get("stock"), 0),
                    barcode=row.get("barcode", "").strip() or None,
                    status="on_sale",
                )
                self.db.add(sku)
                await self.db.flush()
                success += 1

            except Exception as exc:
                failed += 1
                errors.append(f"Row {row_num}: {exc}")
                logger.warning("product.import.row_error", row=row_num, error=str(exc))

        await self.db.flush()
        logger.info("product.import.complete", total=total, success=success, failed=failed)
        return {
            "total": total,
            "success": success,
            "failed": failed,
            "errors": errors,
        }

    # ──────────────────────────────────────────────────────────
    #  Platform Sync Status
    # ──────────────────────────────────────────────────────────

    async def get_platform_sync_status(
        self,
        product_id: str,
    ) -> dict[str, Any]:
        """Return the per-platform sync-status map for a product."""
        product = await self.get_product(product_id)
        return product.platform_sync_status or {}

    async def set_platform_sync_status(
        self,
        product_id: str,
        platform: str,
        state: str,
        platform_product_id: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """Update the sync status for a specific platform on a product."""
        product = await self.get_product(product_id)
        if product.platform_sync_status is None:
            product.platform_sync_status = {}

        product.platform_sync_status[platform] = {
            "platform": platform,
            "state": state,
            "platform_product_id": platform_product_id or "",
            "synced_at": _now_ms(),
            "error_message": error_message or "",
        }
        await self.db.flush()
        return product.platform_sync_status


# ── Internal helpers ──


def _parse_int(value: str | None, default: int = 0) -> int:
    """Parse a string to int, returning default on failure."""
    if value is None:
        return default
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return default
