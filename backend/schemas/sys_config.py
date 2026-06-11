from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SysConfigOut(BaseModel):
    id: int
    config_key: str
    config_value: str
    config_type: str
    description: Optional[str] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class SysConfigUpdate(BaseModel):
    config_value: str
    config_type: Optional[str] = None
    description: Optional[str] = None
