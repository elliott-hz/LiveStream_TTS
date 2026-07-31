from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, new_uuid


class PlatformConfig(Base, TimestampMixin):
    """各平台 API 凭证（平台级，所有直播间共用）"""
    __tablename__ = "platform_configs"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    platform: Mapped[str] = mapped_column(String(20), unique=True)  # taobao / douyin / kuaishou
    app_key: Mapped[str] = mapped_column(String(200), default="")
    app_secret: Mapped[str] = mapped_column(String(200), default="")
    rtmp_template: Mapped[str] = mapped_column(String(500), default="")  # RTMP 地址模板
    is_active: Mapped[bool] = mapped_column(default=False)
    capabilities_json: Mapped[str] = mapped_column(Text, default="{}")  # 能力矩阵 JSON


class SystemSetting(Base):
    """全局偏好设置"""
    __tablename__ = "system_settings"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_uuid)
    key: Mapped[str] = mapped_column(String(100), unique=True)
    value: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(String(200), default="")
