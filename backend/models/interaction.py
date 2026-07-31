from sqlalchemy import String, Text, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, new_uuid


class InteractionConfig(Base, TimestampMixin):
    __tablename__ = "interaction_configs"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    reply_mode: Mapped[str] = mapped_column(String(20), default="tts")       # tts / original_audio
    reply_decision: Mapped[str] = mapped_column(String(20), default="questions_only")
    reply_style: Mapped[str] = mapped_column(String(20), default="warm")     # warm / professional / lively
    tts_speed: Mapped[float] = mapped_column(Float, default=1.0)
    tts_volume: Mapped[float] = mapped_column(Float, default=0.8)
    tts_pitch: Mapped[float] = mapped_column(Float, default=1.0)


class ReplyTemplate(Base, TimestampMixin):
    __tablename__ = "reply_templates"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    product_id: Mapped[str | None] = mapped_column(String(12), ForeignKey("products.id"), nullable=True)
    keywords: Mapped[str] = mapped_column(String(500))
    reply_text: Mapped[str] = mapped_column(Text)
    reply_type: Mapped[str] = mapped_column(String(20), default="voice+text")  # voice+text / text_only
