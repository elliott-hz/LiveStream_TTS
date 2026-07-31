from sqlalchemy import String, Text, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin, new_uuid


class RawVideo(Base, TimestampMixin):
    __tablename__ = "raw_videos"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    file_path: Mapped[str] = mapped_column(String(500))
    file_name: Mapped[str] = mapped_column(String(200))
    duration: Mapped[int] = mapped_column(Integer, default=0)          # 秒
    parse_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / processing / done
    parse_progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100

    segments: Mapped[list["VideoSegment"]] = relationship(
        back_populates="raw_video", cascade="all, delete-orphan", lazy="selectin"
    )


class VideoSegment(Base, TimestampMixin):
    __tablename__ = "video_segments"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    raw_video_id: Mapped[str] = mapped_column(String(12), ForeignKey("raw_videos.id"))
    product_id: Mapped[str | None] = mapped_column(String(12), ForeignKey("products.id"), nullable=True)
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)
    script: Mapped[str] = mapped_column(Text, default="")
    clip_path: Mapped[str] = mapped_column(String(500), default="")  # 切片文件路径
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / published

    raw_video: Mapped["RawVideo"] = relationship(back_populates="segments")


class LiveVideo(Base, TimestampMixin):
    __tablename__ = "live_videos"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200))
    play_mode: Mapped[str] = mapped_column(String(20), default="sequential")  # sequential / random

    clips: Mapped[list["LiveVideoClip"]] = relationship(
        back_populates="live_video", cascade="all, delete-orphan",
        order_by="LiveVideoClip.sort_order", lazy="selectin",
    )


class LiveVideoClip(Base, TimestampMixin):
    __tablename__ = "live_video_clips"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    live_video_id: Mapped[str] = mapped_column(String(12), ForeignKey("live_videos.id"))
    segment_id: Mapped[str] = mapped_column(String(12), ForeignKey("video_segments.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    weight: Mapped[int] = mapped_column(Integer, default=1)         # 1-5
    pause_after: Mapped[int] = mapped_column(Integer, default=0)    # 停顿秒数 0/3/5
    pause_content: Mapped[str] = mapped_column(String(20), default="freeze")  # freeze / card / custom
    closeup: Mapped[str] = mapped_column(String(20), default="off")
    transition: Mapped[str] = mapped_column(String(20), default="none")
    overlay: Mapped[str] = mapped_column(String(20), default="none")
    script_override: Mapped[str] = mapped_column(Text, default="")

    live_video: Mapped["LiveVideo"] = relationship(back_populates="clips")
