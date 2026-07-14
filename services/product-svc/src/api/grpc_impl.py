"""
gRPC service implementation for ProductService.

Maps each RPC to the corresponding ProductService method.
Converts DB ORM models <-> proto messages.
Translates AppError exceptions to gRPC status codes.
"""

from typing import Any, Callable, Coroutine

import grpc
from grpc import aio

from libs.common.errors import AppError, ErrorCode
from libs.common.logging import get_logger

# Generated protobuf modules  (modules/ must be on sys.path)
from product.v1 import product_pb2 as pb
from product.v1 import product_pb2_grpc as pb_grpc
from common.v1 import common_pb2 as common_pb

from models.product import (
    Product,
    Sku,
    ProductImage,
    ProductVideo,
    Category,
)
from services.product_service import ProductService

logger = get_logger(__name__)

# Callable that returns a ProductService instance (one per request).
ServiceFactory = Callable[[], Coroutine[Any, Any, ProductService]]


# ── Exception → gRPC error mapping ──

_ERROR_CODE_TO_GRPC: dict[ErrorCode, grpc.StatusCode] = {
    ErrorCode.UNAUTHENTICATED: grpc.StatusCode.UNAUTHENTICATED,
    ErrorCode.PERMISSION_DENIED: grpc.StatusCode.PERMISSION_DENIED,
    ErrorCode.INVALID_ARGUMENT: grpc.StatusCode.INVALID_ARGUMENT,
    ErrorCode.MISSING_REQUIRED_FIELD: grpc.StatusCode.INVALID_ARGUMENT,
    ErrorCode.NOT_FOUND: grpc.StatusCode.NOT_FOUND,
    ErrorCode.PRODUCT_NOT_FOUND: grpc.StatusCode.NOT_FOUND,
    ErrorCode.DUPLICATE_RESOURCE: grpc.StatusCode.ALREADY_EXISTS,
    ErrorCode.INTERNAL_ERROR: grpc.StatusCode.INTERNAL,
    ErrorCode.DATABASE_ERROR: grpc.StatusCode.INTERNAL,
}


def _app_error_to_grpc_context(exc: AppError, context: aio.ServicerContext) -> None:
    """Set gRPC context status and trailing metadata from an AppError."""
    grpc_code = _ERROR_CODE_TO_GRPC.get(exc.code, grpc.StatusCode.UNKNOWN)
    context.set_code(grpc_code)
    context.set_details(exc.message)
    error_proto = common_pb.Error(
        code=exc.full_code,
        message=exc.message,
        details=exc.details,
    )
    context.set_trailing_metadata(
        ("x-error-code", str(exc.full_code)),
        ("x-error-bin", error_proto.SerializeToString()),
    )


# ── Proto ↔ ORM converters ──


def _product_to_proto(product: Product) -> pb.Product:
    """Convert an ORM Product to a proto Product message."""
    audit = common_pb.AuditInfo(
        created_by=product.created_by or "",
        updated_by=product.updated_by or "",
        timestamps=common_pb.Timestamps(
            created_at=int(product.created_at.timestamp() * 1000),
            updated_at=int(product.updated_at.timestamp() * 1000),
        ),
    )

    return pb.Product(
        product_id=product.product_id,
        store_id=product.store_id,
        title=product.title,
        subtitle=product.subtitle or "",
        description=product.description or "",
        category_path=product.category_path or [],
        brand=product.brand or "",
        images=[_image_to_proto(img) for img in (product.images or [])],
        videos=[_video_to_proto(vid) for vid in (product.videos or [])],
        attributes=product.attributes or {},
        selling_points=product.selling_points or [],
        skus=[_sku_to_proto(sku) for sku in (product.skus or [])],
        platform_sync_status=_sync_status_to_proto(product.platform_sync_status),
        status=_product_status_to_proto(product.status),
        audit_info=audit,
    )


def _sku_to_proto(sku: Sku) -> pb.Sku:
    return pb.Sku(
        sku_id=sku.sku_id,
        spec=sku.spec or {},
        price=common_pb.Money(amount=sku.price, currency="CNY"),
        original_price=common_pb.Money(amount=sku.original_price, currency="CNY"),
        stock=sku.stock,
        barcode=sku.barcode or "",
        status=_sku_status_to_proto(sku.status),
    )


def _image_to_proto(img: ProductImage) -> pb.ProductImage:
    return pb.ProductImage(
        url=img.url,
        type=_image_type_to_proto(img.type),
        width=img.width or 0,
        height=img.height or 0,
        sort_order=img.sort_order,
    )


def _video_to_proto(vid: ProductVideo) -> pb.ProductVideo:
    return pb.ProductVideo(
        url=vid.url,
        type=_video_type_to_proto(vid.type),
        duration_seconds=vid.duration_seconds or 0,
        thumbnail_url=vid.thumbnail_url or "",
    )


def _category_to_proto(cat: Category) -> pb.Category:
    return pb.Category(
        category_id=cat.category_id,
        name=cat.name,
        parent_id=cat.parent_id or "",
        level=cat.level,
        product_count=cat.product_count,
    )


def _sync_status_to_proto(
    status: dict[str, Any] | None,
) -> dict[str, pb.PlatformSyncStatus]:
    """Convert the JSON platform_sync_status dict to proto map."""
    result: dict[str, pb.PlatformSyncStatus] = {}
    if not status:
        return result
    for platform, data in status.items():
        if isinstance(data, dict):
            result[platform] = pb.PlatformSyncStatus(
                platform=data.get("platform", platform),
                state=_sync_state_to_proto(data.get("state", "pending")),
                platform_product_id=data.get("platform_product_id", ""),
                synced_at=data.get("synced_at", 0),
                error_message=data.get("error_message", ""),
            )
    return result


# ── Enum converters (ORM string <-> proto enum) ──

_MAP_PRODUCT_STATUS = {
    "draft": pb.ProductStatus.PRODUCT_STATUS_DRAFT,
    "published": pb.ProductStatus.PRODUCT_STATUS_PUBLISHED,
    "archived": pb.ProductStatus.PRODUCT_STATUS_ARCHIVED,
}
_REV_PRODUCT_STATUS = {v: k for k, v in _MAP_PRODUCT_STATUS.items()}


def _product_status_to_proto(status: str) -> pb.ProductStatus:
    return _MAP_PRODUCT_STATUS.get(status, pb.ProductStatus.PRODUCT_STATUS_DRAFT)


def _product_status_from_proto(status: pb.ProductStatus) -> str:
    return _REV_PRODUCT_STATUS.get(status, "draft")


_MAP_SKU_STATUS = {
    "on_sale": pb.SkuStatus.SKU_STATUS_ON_SALE,
    "off_shelf": pb.SkuStatus.SKU_STATUS_OFF_SHELF,
    "deleted": pb.SkuStatus.SKU_STATUS_DELETED,
}
_REV_SKU_STATUS = {v: k for k, v in _MAP_SKU_STATUS.items()}


def _sku_status_to_proto(status: str) -> pb.SkuStatus:
    return _MAP_SKU_STATUS.get(status, pb.SkuStatus.SKU_STATUS_ON_SALE)


def _sku_status_from_proto(status: pb.SkuStatus) -> str:
    return _REV_SKU_STATUS.get(status, "on_sale")


_MAP_IMAGE_TYPE = {
    "main": pb.ImageType.IMAGE_TYPE_MAIN,
    "detail": pb.ImageType.IMAGE_TYPE_DETAIL,
    "color_variant": pb.ImageType.IMAGE_TYPE_COLOR_VARIANT,
}
_REV_IMAGE_TYPE = {v: k for k, v in _MAP_IMAGE_TYPE.items()}


def _image_type_to_proto(t: str) -> pb.ImageType:
    return _MAP_IMAGE_TYPE.get(t, pb.ImageType.IMAGE_TYPE_MAIN)


def _image_type_from_proto(t: pb.ImageType) -> str:
    return _REV_IMAGE_TYPE.get(t, "main")


_MAP_VIDEO_TYPE = {
    "showcase": pb.VideoType.VIDEO_TYPE_SHOWCASE,
    "demo": pb.VideoType.VIDEO_TYPE_DEMO,
}


def _video_type_to_proto(t: str) -> pb.VideoType:
    return _MAP_VIDEO_TYPE.get(t, pb.VideoType.VIDEO_TYPE_SHOWCASE)


_MAP_SYNC_STATE = {
    "pending": pb.SyncState.SYNC_STATE_PENDING,
    "synced": pb.SyncState.SYNC_STATE_SYNCED,
    "failed": pb.SyncState.SYNC_STATE_FAILED,
    "not_supported": pb.SyncState.SYNC_STATE_NOT_SUPPORTED,
}


def _sync_state_to_proto(s: str) -> pb.SyncState:
    return _MAP_SYNC_STATE.get(s, pb.SyncState.SYNC_STATE_UNSPECIFIED)


# ── Servicer ──


class ProductServiceServicer(pb_grpc.ProductServiceServicer):
    """gRPC servicer that delegates to ProductService for business logic.

    Each RPC call creates a fresh ProductService via ``_svc_factory``
    (an async callable) to guarantee request-scoped DB sessions.
    """

    def __init__(self, product_service_factory: ServiceFactory) -> None:
        self._svc_factory = product_service_factory

    async def _svc(self) -> ProductService:
        """Return a request-scoped ProductService instance."""
        return await self._svc_factory()

    async def _run(
        self,
        handler,
        request,
        context: aio.ServicerContext,
    ) -> Any:
        """Execute ``handler(service, request)`` with AppError translation."""
        try:
            svc = await self._svc()
            return await handler(svc, request)
        except AppError as exc:
            _app_error_to_grpc_context(exc, context)
            return None
        except Exception as exc:
            logger.exception("grpc.handler_error", method=context.method)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return None

    # ──────────────────────────────────────────────────────────
    #  Product CRUD
    # ──────────────────────────────────────────────────────────

    async def CreateProduct(
        self,
        request: pb.CreateProductRequest,
        context: aio.ServicerContext,
    ) -> pb.Product:
        async def handler(svc: ProductService, req: pb.CreateProductRequest) -> pb.Product:
            images_data = [
                {
                    "url": img.url,
                    "type": _image_type_from_proto(img.type),
                    "width": img.width,
                    "height": img.height,
                    "sort_order": img.sort_order,
                }
                for img in req.images
            ]
            product = await svc.create_product(
                store_id=req.store_id,
                title=req.title,
                subtitle=req.subtitle or None,
                description=req.description or None,
                category_path=list(req.category_path) if req.category_path else None,
                brand=req.brand or None,
                images=images_data or None,
                attributes=dict(req.attributes) if req.attributes else None,
                selling_points=list(req.selling_points) if req.selling_points else None,
            )
            return _product_to_proto(product)

        return await self._run(handler, request, context)

    async def GetProduct(
        self,
        request: pb.GetProductRequest,
        context: aio.ServicerContext,
    ) -> pb.Product:
        async def handler(svc: ProductService, req: pb.GetProductRequest) -> pb.Product:
            product = await svc.get_product(product_id=req.product_id)
            return _product_to_proto(product)

        return await self._run(handler, request, context)

    async def UpdateProduct(
        self,
        request: pb.UpdateProductRequest,
        context: aio.ServicerContext,
    ) -> pb.Product:
        async def handler(svc: ProductService, req: pb.UpdateProductRequest) -> pb.Product:
            kwargs: dict[str, Any] = {}
            if req.HasField("title"):
                kwargs["title"] = req.title
            if req.HasField("subtitle"):
                kwargs["subtitle"] = req.subtitle
            if req.HasField("description"):
                kwargs["description"] = req.description
            if req.HasField("status"):
                kwargs["status"] = _product_status_from_proto(req.status)
            product = await svc.update_product(product_id=req.product_id, **kwargs)
            return _product_to_proto(product)

        return await self._run(handler, request, context)

    async def DeleteProduct(
        self,
        request: pb.DeleteProductRequest,
        context: aio.ServicerContext,
    ) -> common_pb.Error:
        async def handler(svc: ProductService, req: pb.DeleteProductRequest) -> common_pb.Error:
            await svc.delete_product(product_id=req.product_id)
            return common_pb.Error(code=0, message="ok")

        return await self._run(handler, request, context)

    async def ListProducts(
        self,
        request: pb.ListProductsRequest,
        context: aio.ServicerContext,
    ) -> pb.ListProductsResponse:
        async def handler(
            svc: ProductService,
            req: pb.ListProductsRequest,
        ) -> pb.ListProductsResponse:
            pagination = req.pagination
            page = pagination.page if pagination and pagination.page else 1
            page_size = pagination.page_size if pagination and pagination.page_size else 20

            products, total_count = await svc.list_products(
                store_id=req.store_id,
                category=req.category or None,
                status=(
                    _product_status_from_proto(req.status)
                    if req.HasField("status")
                    else None
                ),
                search_query=req.search_query or None,
                page=page,
                page_size=page_size,
            )
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            return pb.ListProductsResponse(
                products=[_product_to_proto(p) for p in products],
                page_info=common_pb.PageInfo(
                    page=page,
                    page_size=page_size,
                    total_count=total_count,
                    total_pages=total_pages,
                ),
            )

        return await self._run(handler, request, context)

    # ──────────────────────────────────────────────────────────
    #  SKU Management
    # ──────────────────────────────────────────────────────────

    async def AddSku(
        self,
        request: pb.AddSkuRequest,
        context: aio.ServicerContext,
    ) -> pb.Product:
        async def handler(svc: ProductService, req: pb.AddSkuRequest) -> pb.Product:
            price = req.price.amount if req.price else 0
            original_price = req.original_price.amount if req.original_price else 0
            await svc.add_sku(
                product_id=req.product_id,
                spec=dict(req.spec) if req.spec else None,
                price=price,
                original_price=original_price,
                stock=req.stock,
                barcode=req.barcode or None,
            )
            product = await svc.get_product(product_id=req.product_id)
            return _product_to_proto(product)

        return await self._run(handler, request, context)

    async def UpdateSku(
        self,
        request: pb.UpdateSkuRequest,
        context: aio.ServicerContext,
    ) -> pb.Product:
        async def handler(svc: ProductService, req: pb.UpdateSkuRequest) -> pb.Product:
            kwargs: dict[str, Any] = {}
            if req.HasField("price"):
                kwargs["price"] = req.price.amount
            if req.HasField("stock"):
                kwargs["stock"] = req.stock
            if req.HasField("status"):
                kwargs["status"] = _sku_status_from_proto(req.status)
            await svc.update_sku(
                product_id=req.product_id, sku_id=req.sku_id, **kwargs
            )
            product = await svc.get_product(product_id=req.product_id)
            return _product_to_proto(product)

        return await self._run(handler, request, context)

    async def DeleteSku(
        self,
        request: pb.DeleteSkuRequest,
        context: aio.ServicerContext,
    ) -> pb.Product:
        async def handler(svc: ProductService, req: pb.DeleteSkuRequest) -> pb.Product:
            await svc.delete_sku(product_id=req.product_id, sku_id=req.sku_id)
            product = await svc.get_product(product_id=req.product_id)
            return _product_to_proto(product)

        return await self._run(handler, request, context)

    # ──────────────────────────────────────────────────────────
    #  Category
    # ──────────────────────────────────────────────────────────

    async def ListCategories(
        self,
        request: pb.ListCategoriesRequest,
        context: aio.ServicerContext,
    ) -> pb.ListCategoriesResponse:
        async def handler(
            svc: ProductService,
            req: pb.ListCategoriesRequest,
        ) -> pb.ListCategoriesResponse:
            categories = await svc.list_categories(store_id=req.store_id)
            return pb.ListCategoriesResponse(
                categories=[_category_to_proto(c) for c in categories]
            )

        return await self._run(handler, request, context)

    # ──────────────────────────────────────────────────────────
    #  Import / Export
    # ──────────────────────────────────────────────────────────

    async def ImportProducts(
        self,
        request: pb.ImportProductsRequest,
        context: aio.ServicerContext,
    ) -> pb.ImportProductsResponse:
        async def handler(
            svc: ProductService,
            req: pb.ImportProductsRequest,
        ) -> pb.ImportProductsResponse:
            csv_content: str | None = None
            if req.HasField("csv_content"):
                csv_content = req.csv_content.decode("utf-8")
            elif req.HasField("platform"):
                raise AppError(
                    ErrorCode.INVALID_ARGUMENT,
                    "Platform import not supported yet; use csv_content",
                )
            else:
                raise AppError(
                    ErrorCode.INVALID_ARGUMENT,
                    "Either csv_content or platform must be provided",
                )

            result = await svc.import_products(
                store_id=req.store_id,
                csv_content=csv_content,
            )
            return pb.ImportProductsResponse(
                total=result["total"],
                success=result["success"],
                failed=result["failed"],
                errors=result["errors"],
            )

        return await self._run(handler, request, context)

    # ──────────────────────────────────────────────────────────
    #  Platform Sync Status
    # ──────────────────────────────────────────────────────────

    async def GetPlatformSyncStatus(
        self,
        request: pb.GetPlatformSyncStatusRequest,
        context: aio.ServicerContext,
    ) -> pb.PlatformSyncStatus:
        async def handler(
            svc: ProductService,
            req: pb.GetPlatformSyncStatusRequest,
        ) -> pb.PlatformSyncStatus:
            status_map = await svc.get_platform_sync_status(product_id=req.product_id)
            if status_map:
                first_key = next(iter(status_map))
                data = status_map[first_key]
                return pb.PlatformSyncStatus(
                    platform=first_key,
                    state=_sync_state_to_proto(data.get("state", "pending")),
                    platform_product_id=data.get("platform_product_id", ""),
                    synced_at=data.get("synced_at", 0),
                    error_message=data.get("error_message", ""),
                )
            return pb.PlatformSyncStatus(
                platform="", state=pb.SyncState.SYNC_STATE_UNSPECIFIED
            )

        return await self._run(handler, request, context)
