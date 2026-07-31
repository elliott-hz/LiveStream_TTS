from datetime import datetime
from pydantic import BaseModel


class UserOut(BaseModel):
    id: str
    username: str
    role: str
    quota_hours: float | None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str
    role: str = "editor"
    quota_hours: float | None = None  # None = 共享主账号时长


class MerchantOut(BaseModel):
    id: str
    name: str
    tier: str
    subscribed_until: datetime | None
    max_rooms: int
    max_streams: int

    model_config = {"from_attributes": True}


class MerchantUpdate(BaseModel):
    name: str | None = None
    tier: str | None = None
