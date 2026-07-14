from common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ImageType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    IMAGE_TYPE_UNSPECIFIED: _ClassVar[ImageType]
    IMAGE_TYPE_MAIN: _ClassVar[ImageType]
    IMAGE_TYPE_DETAIL: _ClassVar[ImageType]
    IMAGE_TYPE_COLOR_VARIANT: _ClassVar[ImageType]

class VideoType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    VIDEO_TYPE_UNSPECIFIED: _ClassVar[VideoType]
    VIDEO_TYPE_SHOWCASE: _ClassVar[VideoType]
    VIDEO_TYPE_DEMO: _ClassVar[VideoType]

class SkuStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SKU_STATUS_UNSPECIFIED: _ClassVar[SkuStatus]
    SKU_STATUS_ON_SALE: _ClassVar[SkuStatus]
    SKU_STATUS_OFF_SHELF: _ClassVar[SkuStatus]
    SKU_STATUS_DELETED: _ClassVar[SkuStatus]

class ProductStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PRODUCT_STATUS_UNSPECIFIED: _ClassVar[ProductStatus]
    PRODUCT_STATUS_DRAFT: _ClassVar[ProductStatus]
    PRODUCT_STATUS_PUBLISHED: _ClassVar[ProductStatus]
    PRODUCT_STATUS_ARCHIVED: _ClassVar[ProductStatus]

class SyncState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SYNC_STATE_UNSPECIFIED: _ClassVar[SyncState]
    SYNC_STATE_PENDING: _ClassVar[SyncState]
    SYNC_STATE_SYNCED: _ClassVar[SyncState]
    SYNC_STATE_FAILED: _ClassVar[SyncState]
    SYNC_STATE_NOT_SUPPORTED: _ClassVar[SyncState]
IMAGE_TYPE_UNSPECIFIED: ImageType
IMAGE_TYPE_MAIN: ImageType
IMAGE_TYPE_DETAIL: ImageType
IMAGE_TYPE_COLOR_VARIANT: ImageType
VIDEO_TYPE_UNSPECIFIED: VideoType
VIDEO_TYPE_SHOWCASE: VideoType
VIDEO_TYPE_DEMO: VideoType
SKU_STATUS_UNSPECIFIED: SkuStatus
SKU_STATUS_ON_SALE: SkuStatus
SKU_STATUS_OFF_SHELF: SkuStatus
SKU_STATUS_DELETED: SkuStatus
PRODUCT_STATUS_UNSPECIFIED: ProductStatus
PRODUCT_STATUS_DRAFT: ProductStatus
PRODUCT_STATUS_PUBLISHED: ProductStatus
PRODUCT_STATUS_ARCHIVED: ProductStatus
SYNC_STATE_UNSPECIFIED: SyncState
SYNC_STATE_PENDING: SyncState
SYNC_STATE_SYNCED: SyncState
SYNC_STATE_FAILED: SyncState
SYNC_STATE_NOT_SUPPORTED: SyncState

class Product(_message.Message):
    __slots__ = ("product_id", "store_id", "title", "subtitle", "description", "category_path", "brand", "images", "videos", "attributes", "selling_points", "skus", "platform_sync_status", "status", "audit_info")
    class AttributesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    class PlatformSyncStatusEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: PlatformSyncStatus
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[PlatformSyncStatus, _Mapping]] = ...) -> None: ...
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    SUBTITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_PATH_FIELD_NUMBER: _ClassVar[int]
    BRAND_FIELD_NUMBER: _ClassVar[int]
    IMAGES_FIELD_NUMBER: _ClassVar[int]
    VIDEOS_FIELD_NUMBER: _ClassVar[int]
    ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    SELLING_POINTS_FIELD_NUMBER: _ClassVar[int]
    SKUS_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_SYNC_STATUS_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    AUDIT_INFO_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    store_id: str
    title: str
    subtitle: str
    description: str
    category_path: _containers.RepeatedScalarFieldContainer[str]
    brand: str
    images: _containers.RepeatedCompositeFieldContainer[ProductImage]
    videos: _containers.RepeatedCompositeFieldContainer[ProductVideo]
    attributes: _containers.ScalarMap[str, str]
    selling_points: _containers.RepeatedScalarFieldContainer[str]
    skus: _containers.RepeatedCompositeFieldContainer[Sku]
    platform_sync_status: _containers.MessageMap[str, PlatformSyncStatus]
    status: ProductStatus
    audit_info: _common_pb2.AuditInfo
    def __init__(self, product_id: _Optional[str] = ..., store_id: _Optional[str] = ..., title: _Optional[str] = ..., subtitle: _Optional[str] = ..., description: _Optional[str] = ..., category_path: _Optional[_Iterable[str]] = ..., brand: _Optional[str] = ..., images: _Optional[_Iterable[_Union[ProductImage, _Mapping]]] = ..., videos: _Optional[_Iterable[_Union[ProductVideo, _Mapping]]] = ..., attributes: _Optional[_Mapping[str, str]] = ..., selling_points: _Optional[_Iterable[str]] = ..., skus: _Optional[_Iterable[_Union[Sku, _Mapping]]] = ..., platform_sync_status: _Optional[_Mapping[str, PlatformSyncStatus]] = ..., status: _Optional[_Union[ProductStatus, str]] = ..., audit_info: _Optional[_Union[_common_pb2.AuditInfo, _Mapping]] = ...) -> None: ...

class ProductImage(_message.Message):
    __slots__ = ("url", "type", "width", "height", "sort_order")
    URL_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    WIDTH_FIELD_NUMBER: _ClassVar[int]
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    url: str
    type: ImageType
    width: int
    height: int
    sort_order: int
    def __init__(self, url: _Optional[str] = ..., type: _Optional[_Union[ImageType, str]] = ..., width: _Optional[int] = ..., height: _Optional[int] = ..., sort_order: _Optional[int] = ...) -> None: ...

class ProductVideo(_message.Message):
    __slots__ = ("url", "type", "duration_seconds", "thumbnail_url")
    URL_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DURATION_SECONDS_FIELD_NUMBER: _ClassVar[int]
    THUMBNAIL_URL_FIELD_NUMBER: _ClassVar[int]
    url: str
    type: VideoType
    duration_seconds: int
    thumbnail_url: str
    def __init__(self, url: _Optional[str] = ..., type: _Optional[_Union[VideoType, str]] = ..., duration_seconds: _Optional[int] = ..., thumbnail_url: _Optional[str] = ...) -> None: ...

class Sku(_message.Message):
    __slots__ = ("sku_id", "spec", "price", "original_price", "stock", "barcode", "status")
    class SpecEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    SKU_ID_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    ORIGINAL_PRICE_FIELD_NUMBER: _ClassVar[int]
    STOCK_FIELD_NUMBER: _ClassVar[int]
    BARCODE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    sku_id: str
    spec: _containers.ScalarMap[str, str]
    price: _common_pb2.Money
    original_price: _common_pb2.Money
    stock: int
    barcode: str
    status: SkuStatus
    def __init__(self, sku_id: _Optional[str] = ..., spec: _Optional[_Mapping[str, str]] = ..., price: _Optional[_Union[_common_pb2.Money, _Mapping]] = ..., original_price: _Optional[_Union[_common_pb2.Money, _Mapping]] = ..., stock: _Optional[int] = ..., barcode: _Optional[str] = ..., status: _Optional[_Union[SkuStatus, str]] = ...) -> None: ...

class PlatformSyncStatus(_message.Message):
    __slots__ = ("platform", "state", "platform_product_id", "synced_at", "error_message")
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    SYNCED_AT_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    platform: str
    state: SyncState
    platform_product_id: str
    synced_at: int
    error_message: str
    def __init__(self, platform: _Optional[str] = ..., state: _Optional[_Union[SyncState, str]] = ..., platform_product_id: _Optional[str] = ..., synced_at: _Optional[int] = ..., error_message: _Optional[str] = ...) -> None: ...

class CreateProductRequest(_message.Message):
    __slots__ = ("store_id", "title", "subtitle", "description", "category_path", "brand", "images", "attributes", "selling_points")
    class AttributesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    SUBTITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_PATH_FIELD_NUMBER: _ClassVar[int]
    BRAND_FIELD_NUMBER: _ClassVar[int]
    IMAGES_FIELD_NUMBER: _ClassVar[int]
    ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    SELLING_POINTS_FIELD_NUMBER: _ClassVar[int]
    store_id: str
    title: str
    subtitle: str
    description: str
    category_path: _containers.RepeatedScalarFieldContainer[str]
    brand: str
    images: _containers.RepeatedCompositeFieldContainer[ProductImage]
    attributes: _containers.ScalarMap[str, str]
    selling_points: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, store_id: _Optional[str] = ..., title: _Optional[str] = ..., subtitle: _Optional[str] = ..., description: _Optional[str] = ..., category_path: _Optional[_Iterable[str]] = ..., brand: _Optional[str] = ..., images: _Optional[_Iterable[_Union[ProductImage, _Mapping]]] = ..., attributes: _Optional[_Mapping[str, str]] = ..., selling_points: _Optional[_Iterable[str]] = ...) -> None: ...

class GetProductRequest(_message.Message):
    __slots__ = ("product_id",)
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    def __init__(self, product_id: _Optional[str] = ...) -> None: ...

class UpdateProductRequest(_message.Message):
    __slots__ = ("product_id", "title", "subtitle", "description", "status")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    SUBTITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    title: str
    subtitle: str
    description: str
    status: ProductStatus
    def __init__(self, product_id: _Optional[str] = ..., title: _Optional[str] = ..., subtitle: _Optional[str] = ..., description: _Optional[str] = ..., status: _Optional[_Union[ProductStatus, str]] = ...) -> None: ...

class DeleteProductRequest(_message.Message):
    __slots__ = ("product_id",)
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    def __init__(self, product_id: _Optional[str] = ...) -> None: ...

class ListProductsRequest(_message.Message):
    __slots__ = ("store_id", "category", "status", "search_query", "pagination")
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    SEARCH_QUERY_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    store_id: str
    category: str
    status: ProductStatus
    search_query: str
    pagination: _common_pb2.Pagination
    def __init__(self, store_id: _Optional[str] = ..., category: _Optional[str] = ..., status: _Optional[_Union[ProductStatus, str]] = ..., search_query: _Optional[str] = ..., pagination: _Optional[_Union[_common_pb2.Pagination, _Mapping]] = ...) -> None: ...

class ListProductsResponse(_message.Message):
    __slots__ = ("products", "page_info")
    PRODUCTS_FIELD_NUMBER: _ClassVar[int]
    PAGE_INFO_FIELD_NUMBER: _ClassVar[int]
    products: _containers.RepeatedCompositeFieldContainer[Product]
    page_info: _common_pb2.PageInfo
    def __init__(self, products: _Optional[_Iterable[_Union[Product, _Mapping]]] = ..., page_info: _Optional[_Union[_common_pb2.PageInfo, _Mapping]] = ...) -> None: ...

class AddSkuRequest(_message.Message):
    __slots__ = ("product_id", "spec", "price", "original_price", "stock", "barcode")
    class SpecEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    ORIGINAL_PRICE_FIELD_NUMBER: _ClassVar[int]
    STOCK_FIELD_NUMBER: _ClassVar[int]
    BARCODE_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    spec: _containers.ScalarMap[str, str]
    price: _common_pb2.Money
    original_price: _common_pb2.Money
    stock: int
    barcode: str
    def __init__(self, product_id: _Optional[str] = ..., spec: _Optional[_Mapping[str, str]] = ..., price: _Optional[_Union[_common_pb2.Money, _Mapping]] = ..., original_price: _Optional[_Union[_common_pb2.Money, _Mapping]] = ..., stock: _Optional[int] = ..., barcode: _Optional[str] = ...) -> None: ...

class UpdateSkuRequest(_message.Message):
    __slots__ = ("product_id", "sku_id", "price", "stock", "status")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    SKU_ID_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    STOCK_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    sku_id: str
    price: _common_pb2.Money
    stock: int
    status: SkuStatus
    def __init__(self, product_id: _Optional[str] = ..., sku_id: _Optional[str] = ..., price: _Optional[_Union[_common_pb2.Money, _Mapping]] = ..., stock: _Optional[int] = ..., status: _Optional[_Union[SkuStatus, str]] = ...) -> None: ...

class DeleteSkuRequest(_message.Message):
    __slots__ = ("product_id", "sku_id")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    SKU_ID_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    sku_id: str
    def __init__(self, product_id: _Optional[str] = ..., sku_id: _Optional[str] = ...) -> None: ...

class ListCategoriesRequest(_message.Message):
    __slots__ = ("store_id",)
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    store_id: str
    def __init__(self, store_id: _Optional[str] = ...) -> None: ...

class ListCategoriesResponse(_message.Message):
    __slots__ = ("categories",)
    CATEGORIES_FIELD_NUMBER: _ClassVar[int]
    categories: _containers.RepeatedCompositeFieldContainer[Category]
    def __init__(self, categories: _Optional[_Iterable[_Union[Category, _Mapping]]] = ...) -> None: ...

class Category(_message.Message):
    __slots__ = ("category_id", "name", "parent_id", "level", "product_count")
    CATEGORY_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_COUNT_FIELD_NUMBER: _ClassVar[int]
    category_id: str
    name: str
    parent_id: str
    level: int
    product_count: int
    def __init__(self, category_id: _Optional[str] = ..., name: _Optional[str] = ..., parent_id: _Optional[str] = ..., level: _Optional[int] = ..., product_count: _Optional[int] = ...) -> None: ...

class ImportProductsRequest(_message.Message):
    __slots__ = ("store_id", "csv_url", "csv_content", "platform")
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    CSV_URL_FIELD_NUMBER: _ClassVar[int]
    CSV_CONTENT_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    store_id: str
    csv_url: str
    csv_content: bytes
    platform: str
    def __init__(self, store_id: _Optional[str] = ..., csv_url: _Optional[str] = ..., csv_content: _Optional[bytes] = ..., platform: _Optional[str] = ...) -> None: ...

class ImportProductsResponse(_message.Message):
    __slots__ = ("total", "success", "failed", "errors")
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    FAILED_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    total: int
    success: int
    failed: int
    errors: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, total: _Optional[int] = ..., success: _Optional[int] = ..., failed: _Optional[int] = ..., errors: _Optional[_Iterable[str]] = ...) -> None: ...

class GetPlatformSyncStatusRequest(_message.Message):
    __slots__ = ("product_id",)
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    def __init__(self, product_id: _Optional[str] = ...) -> None: ...
