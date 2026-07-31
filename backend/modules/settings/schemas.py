from pydantic import BaseModel


class SettingOut(BaseModel):
    key: str
    value: str
    description: str

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    value: str


class AllSettingsOut(BaseModel):
    settings: list[SettingOut]
