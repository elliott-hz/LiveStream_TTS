"""
FastAPI HTTP routes for product-svc.

Provides REST-style endpoints that mirror the gRPC API for
convenience of external integrations and health checks.
"""

from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError
from libs.common.logging import get_logger

from models.product import Product
from .services.product_service import ProductService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1")


# ── Dependency injection ──
# The FastAPI app sets this at startup.
_get_db: Any = None


def configure_routes(get_db_callable: Any) -> None:
    """Wire the database session factory into routes.

    Called once during server startup (main.py).
    """
    global _get_db
    _get_db = get_db_callable


async def _get_service() -> AsyncIterator[ProductService]:
    """FastAPI dependency: yield a ProductService with a request-scoped session."""
    if _get_db is None:
        raise RuntimeError("Routes not configured — call configure_routes first")
    async with _get_db() as session:
        yield ProductService(db=session)


# ── Health ──


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "product-svc"}


# ── Products ──


@router.get("/products")
async def list_products(
    store_id: str = Query(..., description="Store ID"),
    category: str | None = Query(None),
    status: str | None = Query(None),
    search_query: str | None = Query(None, alias="search"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: ProductService = Depends(_get_service),
) -> dict[str, Any]:
    """List products with optional filters and pagination."""
    try:
        products, total = await svc.list_products(
            store_id=store_id,
            category=category,
            status=status,
            search_query=search_query,
            page=page,
            page_size=page_size,
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)

    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "products": [_product_dict(p) for p in products],
        "page_info": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": total_pages,
        },
    }


@router.post("/products", status_code=201)
async def create_product(
    body: dict[str, Any],
    svc: ProductService = Depends(_get_service),
) -> dict[str, Any]:
    """Create a new product."""
    try:
        product = await svc.create_product(
            store_id=body.get("store_id", ""),
            title=body.get("title", ""),
            subtitle=body.get("subtitle"),
            description=body.get("description"),
            category_path=body.get("category_path"),
            brand=body.get("brand"),
            images=body.get("images"),
            attributes=body.get("attributes"),
            selling_points=body.get("selling_points"),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)

    return _product_dict(product)


@router.get("/products/{product_id}")
async def get_product(
    product_id: str,
    svc: ProductService = Depends(_get_service),
) -> dict[str, Any]:
    """Get a single product by ID."""
    try:
        product = await svc.get_product(product_id=product_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _product_dict(product)


@router.put("/products/{product_id}")
async def update_product(
    product_id: str,
    body: dict[str, Any],
    svc: ProductService = Depends(_get_service),
) -> dict[str, Any]:
    """Partially update a product."""
    try:
        product = await svc.update_product(
            product_id=product_id,
            title=body.get("title"),
            subtitle=body.get("subtitle"),
            description=body.get("description"),
            status=body.get("status"),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _product_dict(product)


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    svc: ProductService = Depends(_get_service),
) -> None:
    """Delete a product."""
    try:
        await svc.delete_product(product_id=product_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)


@router.post("/products/{product_id}/skus", status_code=201)
async def add_sku(
    product_id: str,
    body: dict[str, Any],
    svc: ProductService = Depends(_get_service),
) -> dict[str, Any]:
    """Add a SKU to a product."""
    try:
        sku = await svc.add_sku(
            product_id=product_id,
            spec=body.get("spec"),
            price=body.get("price", 0),
            original_price=body.get("original_price", 0),
            stock=body.get("stock", 0),
            barcode=body.get("barcode"),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _sku_dict(sku)


# ── Converters ──


def _product_dict(product: Product) -> dict[str, Any]:
    return {
        "product_id": product.product_id,
        "store_id": product.store_id,
        "title": product.title,
        "subtitle": product.subtitle or "",
        "description": product.description or "",
        "category_path": product.category_path or [],
        "brand": product.brand or "",
        "attributes": product.attributes or {},
        "selling_points": product.selling_points or [],
        "status": product.status,
        "platform_sync_status": product.platform_sync_status or {},
        "skus": [_sku_dict(s) for s in (product.skus or [])],
        "images": [
            {
                "image_id": img.image_id,
                "url": img.url,
                "type": img.type,
                "width": img.width,
                "height": img.height,
                "sort_order": img.sort_order,
            }
            for img in (product.images or [])
        ],
        "videos": [
            {
                "video_id": vid.video_id,
                "url": vid.url,
                "type": vid.type,
                "duration_seconds": vid.duration_seconds,
                "thumbnail_url": vid.thumbnail_url,
            }
            for vid in (product.videos or [])
        ],
        "created_by": product.created_by or "",
        "updated_by": product.updated_by or "",
        "created_at": int(product.created_at.timestamp() * 1000),
        "updated_at": int(product.updated_at.timestamp() * 1000),
    }


def _sku_dict(sku: Any) -> dict[str, Any]:
    return {
        "sku_id": sku.sku_id,
        "product_id": sku.product_id,
        "spec": sku.spec or {},
        "price": sku.price,
        "original_price": sku.original_price,
        "stock": sku.stock,
        "barcode": sku.barcode or "",
        "status": sku.status,
    }


def _app_error_status(exc: AppError) -> int:
    """Map AppError error code to HTTP status."""
    code = exc.code.value if hasattr(exc.code, "value") else exc.code
    if 1001 <= code <= 1004:
        return 401 if code == 1001 else 403
    if 2001 <= code <= 2004:
        return 400
    if 3001 <= code <= 3008:
        return 404
    if 4001 <= code <= 4007:
        return 409
    return 500
