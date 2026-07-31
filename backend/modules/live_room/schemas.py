from pydantic import BaseModel


class RoomCreate(BaseModel):
    name: str
    platform: str = "taobao"
    rtmp_url: str


class RoomUpdate(BaseModel):
    name: str | None = None
    rtmp_url: str | None = None


class RoomOut(BaseModel):
    id: str
    name: str
    platform: str
    rtmp_url: str
    status: str
    attached_video_id: str | None

    model_config = {"from_attributes": True}


class ScheduleIn(BaseModel):
    enabled: bool = False
    start_time: str | None = None   # "08:00"
    end_time: str | None = None     # "22:00"


class ScheduleOut(BaseModel):
    id: str
    enabled: bool
    start_time: str | None
    end_time: str | None

    model_config = {"from_attributes": True}
