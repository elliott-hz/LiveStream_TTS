from pydantic import BaseModel


class PlatformConfigOut(BaseModel):
    id: str
    platform: str
    app_key: str
    is_active: bool
    capabilities_json: str

    model_config = {"from_attributes": True}


class PlatformConfigUpdate(BaseModel):
    app_key: str | None = None
    app_secret: str | None = None
    rtmp_template: str | None = None


class PlatformCapabilityInfo(BaseModel):
    """平台能力矩阵（用于前端展示）"""
    platform: str
    name: str           # 中文名
    icon: str           # emoji
    is_connected: bool
    capabilities: dict  # {stream: true, danmaku: true, ...}
