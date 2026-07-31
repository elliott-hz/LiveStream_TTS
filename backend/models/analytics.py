from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, new_uuid


class LiveSession(Base):
    __tablename__ = "live_sessions"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    room_id: Mapped[str] = mapped_column(String(12), ForeignKey("live_rooms.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    viewers_peak: Mapped[int] = mapped_column(Integer, default=0)
    danmaku_total: Mapped[int] = mapped_column(Integer, default=0)
    ai_reply_total: Mapped[int] = mapped_column(Integer, default=0)
    product_pop_total: Mapped[int] = mapped_column(Integer, default=0)
    orders: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)


class DanmakuRecord(Base):
    __tablename__ = "danmaku_records"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(String(12), ForeignKey("live_sessions.id"))
    user_name: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(20), default="comment")  # comment / question / order_intent
    ai_reply: Mapped[str] = mapped_column(Text, default="")
    reply_latency_ms: Mapped[int] = mapped_column(Integer, default=0)
