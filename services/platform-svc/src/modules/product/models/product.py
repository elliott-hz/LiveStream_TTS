"""
SQLAlchemy 2.0 ORM models for Product, SKU, Category, and related entities.

All models use UUID primary keys and async-compatible types.
Uses generic ``JSON`` type for cross-DB compatibility (works with
both PostgreSQL and SQLite for testing).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.db import Base


# ── Cross-DB JSON type ──
# Prefer PostgreSQL JSON (with operator support), fallback to generic JSON.

try:
    from sqlalchemy.dialects.postgresql import JSON as _JSONType
except ImportError:
    from sqlalchemy import JSON as _JSONType  # type: ignore[assignment]


def _uuid() -> str:
    """Generate a UUID4 hex string for use as a primary key."""
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    """Return current UTC datetime."""
    return datetime.utcnow()


# ── Product ──


class Product(Base):
    """Product master record — core entity for the platform."""

    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=_uuid
    )
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_path: Mapped[list[Any] | None] = mapped_column(
        _JSONType, nullable=True,
        comment="JSON array of category names, e.g. ['女装','连衣裙']",
    )
    brand: Mapped[str | None] = mapped_column(String(256), nullable=True)
    attributes: Mapped[dict[str, str] | None] = mapped_column(
        _JSONType, nullable=True, comment="Key-value attributes, e.g. {'材质':'棉'}",
    )
    selling_points: Mapped[list[str] | None] = mapped_column(
        _JSONType, nullable=True, comment="JSON array of selling point strings",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", index=True
    )
    platform_sync_status: Mapped[dict[str, Any] | None] = mapped_column(
        _JSONType, nullable=True,
        comment=(
            "Per-platform sync state, "
            "e.g. {'taobao': {'state':'synced','platform_product_id':'...'}}"
        ),
    )
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )

    # Relationships
    skus: Mapped[list["Sku"]] = relationship(
        "Sku",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    images: Mapped[list["ProductImage"]] = relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    videos: Mapped[list["ProductVideo"]] = relationship(
        "ProductVideo",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Product {self.product_id} '{self.title}'>"


# ── SKU ──


class Sku(Base):
    """Stock Keeping Unit — variant of a product."""

    __tablename__ = "skus"

    sku_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=_uuid
    )
    product_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    spec: Mapped[dict[str, str] | None] = mapped_column(
        _JSONType, nullable=True,
        comment="Specification, e.g. {'颜色':'黑色','尺码':'M'}",
    )
    price: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Price in fen (cents)"
    )
    original_price: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Original price in fen"
    )
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    barcode: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="on_sale", index=True
    )

    # Relationship
    product: Mapped["Product"] = relationship("Product", back_populates="skus")

    def __repr__(self) -> str:
        return f"<Sku {self.sku_id} (product={self.product_id}) price={self.price}>"


# ── ProductImage ──


class ProductImage(Base):
    """Image attached to a product."""

    __tablename__ = "product_images"

    image_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=_uuid
    )
    product_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="main",
        comment="main / detail / color_variant",
    )
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationship
    product: Mapped["Product"] = relationship("Product", back_populates="images")

    def __repr__(self) -> str:
        return f"<ProductImage {self.url[:40]} type={self.type}>"


# ── ProductVideo ──


class ProductVideo(Base):
    """Video attached to a product (showcase / demo)."""

    __tablename__ = "product_videos"

    video_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=_uuid
    )
    product_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="showcase",
        comment="showcase / demo",
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Relationship
    product: Mapped["Product"] = relationship("Product", back_populates="videos")

    def __repr__(self) -> str:
        return f"<ProductVideo {self.url[:40]} type={self.type}>"


# ── Category ──


class Category(Base):
    """Product category tree node."""

    __tablename__ = "categories"

    category_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=_uuid
    )
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Parent category ID (null for root)"
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    product_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<Category {self.name} (level={self.level})>"
