from pydantic import BaseModel


class InteractionConfigOut(BaseModel):
    id: str
    reply_mode: str
    reply_decision: str
    reply_style: str
    tts_speed: float
    tts_volume: float
    tts_pitch: float

    model_config = {"from_attributes": True}


class InteractionConfigUpdate(BaseModel):
    reply_mode: str | None = None
    reply_decision: str | None = None
    reply_style: str | None = None
    tts_speed: float | None = None
    tts_volume: float | None = None
    tts_pitch: float | None = None


class ReplyTemplateCreate(BaseModel):
    product_id: str | None = None
    keywords: str
    reply_text: str
    reply_type: str = "voice+text"


class ReplyTemplateOut(BaseModel):
    id: str
    product_id: str | None
    keywords: str
    reply_text: str
    reply_type: str

    model_config = {"from_attributes": True}
