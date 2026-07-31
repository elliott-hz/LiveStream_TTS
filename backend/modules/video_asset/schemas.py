from pydantic import BaseModel


class SegmentOut(BaseModel):
    id: str
    product_id: str | None
    start_time: float
    end_time: float
    script: str
    clip_path: str
    status: str

    model_config = {"from_attributes": True}


class RawVideoOut(BaseModel):
    id: str
    file_name: str
    duration: int
    parse_status: str
    parse_progress: float
    segments: list[SegmentOut] = []

    model_config = {"from_attributes": True}


class SegmentUpdate(BaseModel):
    start_time: float | None = None
    end_time: float | None = None
    product_id: str | None = None
    script: str | None = None
