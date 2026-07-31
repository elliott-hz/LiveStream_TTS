from pydantic import BaseModel


class LiveVideoClipIn(BaseModel):
    segment_id: str
    sort_order: int = 0
    weight: int = 1
    pause_after: int = 0
    pause_content: str = "freeze"
    closeup: str = "off"
    transition: str = "none"
    overlay: str = "none"
    script_override: str = ""


class LiveVideoClipOut(BaseModel):
    id: str
    segment_id: str
    sort_order: int
    weight: int
    pause_after: int
    pause_content: str
    closeup: str
    transition: str
    overlay: str
    script_override: str

    model_config = {"from_attributes": True}


class LiveVideoCreate(BaseModel):
    name: str
    play_mode: str = "sequential"


class LiveVideoOut(BaseModel):
    id: str
    name: str
    play_mode: str
    clips: list[LiveVideoClipOut] = []

    model_config = {"from_attributes": True}


class LiveVideoUpdate(BaseModel):
    name: str | None = None
    play_mode: str | None = None
