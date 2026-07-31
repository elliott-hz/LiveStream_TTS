from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin, new_uuid


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200))
    sku: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(50), default="")

    platform_kbs: Mapped[list["ProductKB"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )


class ProductKB(Base, TimestampMixin):
    __tablename__ = "product_kbs"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    product_id: Mapped[str] = mapped_column(String(12), ForeignKey("products.id"))
    platform: Mapped[str] = mapped_column(String(20))       # taobao / douyin / kuaishou / jd / pdd
    platform_name: Mapped[str] = mapped_column(String(200))  # 平台上的商品名
    platform_sku: Mapped[str] = mapped_column(String(100))   # 平台 SKU ID
    price: Mapped[str] = mapped_column(String(20), default="")
    detail_html: Mapped[str] = mapped_column(Text, default="")  # 富文本详情

    product: Mapped["Product"] = relationship(back_populates="platform_kbs")
