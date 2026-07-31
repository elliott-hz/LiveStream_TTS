from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, new_uuid


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200))           # "张老板的店铺"
    tier: Mapped[str] = mapped_column(String(20), default="basic")  # basic / pro / enterprise
    subscribed_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    max_rooms: Mapped[int] = mapped_column(Integer, default=3)
    max_streams: Mapped[int] = mapped_column(Integer, default=1)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    merchant_id: Mapped[str] = mapped_column(String(12), ForeignKey("merchants.id"))
    username: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="editor")  # merchant_admin / editor / viewer
    quota_hours: Mapped[float | None] = mapped_column(Float, nullable=True)  # NULL=共享主账号时长
