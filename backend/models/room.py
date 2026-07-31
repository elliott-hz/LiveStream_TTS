from sqlalchemy import String, Boolean, Time, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, new_uuid


class LiveRoom(Base, TimestampMixin):
    __tablename__ = "live_rooms"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(20), default="taobao")
    rtmp_url: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="idle")  # idle / live
    attached_video_id: Mapped[str | None] = mapped_column(String(12), ForeignKey("live_videos.id"), nullable=True)


class RoomSchedule(Base, TimestampMixin):
    __tablename__ = "room_schedules"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    room_id: Mapped[str] = mapped_column(String(12), ForeignKey("live_rooms.id"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    start_time: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "08:00"
    end_time: Mapped[str | None] = mapped_column(String(5), nullable=True)    # "22:00"
