from pydantic import BaseModel


class ProductKBSchema(BaseModel):
    platform: str
    platform_name: str = ""
    platform_sku: str = ""
    price: str = ""
    detail_html: str = ""

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    name: str
    sku: str
    category: str = ""


class ProductUpdate(BaseModel):
    name: str | None = None
    sku: str | None = None
    category: str | None = None


class ProductOut(BaseModel):
    id: str
    name: str
    sku: str
    category: str
    platform_kbs: list[ProductKBSchema] = []

    model_config = {"from_attributes": True}


class ProductImportRequest(BaseModel):
    platform: str       # taobao / douyin
    url: str            # 商品链接
    product_id: str | None = None  # 关联已有商品（为空则创建新商品）
