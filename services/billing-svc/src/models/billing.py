"""
SQLAlchemy ORM models for billing.

Plans, subscriptions, invoices, payments, and usage tracking.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

try:
    from sqlalchemy.dialects.postgresql import JSON as _JSONType
except ImportError:
    from sqlalchemy import JSON as _JSONType

from libs.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.utcnow()


class Plan(Base):
    """Subscription plan definition."""

    __tablename__ = "plans"

    plan_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    monthly_price_fen: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Price in fen"
    )
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    quota_json: Mapped[dict[str, Any] | None] = mapped_column(
        _JSONType, nullable=True, comment="PlanQuota as JSON"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Plan {self.plan_id} '{self.name}'>"


class Subscription(Base):
    """A store's active/cancelled subscription."""

    __tablename__ = "subscriptions"

    subscription_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )
    started_at: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Subscription {self.subscription_id} store={self.store_id}>"


class Invoice(Base):
    """Invoice generated for a store."""

    __tablename__ = "invoices"

    invoice_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    billing_period: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="e.g. '2026-07'"
    )
    amount_fen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    pdf_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    issued_at: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paid_at: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_id} store={self.store_id} {self.status}>"


class Payment(Base):
    """Payment transaction record."""

    __tablename__ = "payments"

    payment_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    invoice_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    method: Mapped[str] = mapped_column(
        String(32), nullable=False, default="wechat",
        comment="wechat / alipay",
    )
    amount_fen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    qr_code_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    payment_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Payment {self.payment_id} invoice={self.invoice_id}>"


class Usage(Base):
    """Usage record for a store within a billing period."""

    __tablename__ = "usage_records"

    usage_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    billing_period: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="e.g. '2026-07'"
    )
    streaming_minutes_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    streaming_minutes_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    api_calls_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_fen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<Usage {self.store_id} period={self.billing_period}>"
