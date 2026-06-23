from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class TriggerTypeEnum(str, Enum):
    interval = "interval"
    cron = "cron"


class IntervalUnitEnum(str, Enum):
    minutes = "minutes"
    hours = "hours"
    days = "days"


class TriggerCreate(BaseModel):
    """创建触发器的请求体"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    trigger_type: TriggerTypeEnum
    interval_value: Optional[int] = Field(None, ge=1, le=99999)
    interval_unit: Optional[IntervalUnitEnum] = None
    cron_expression: Optional[str] = Field(None, max_length=100)
    app_id: int
    message: str = Field(..., min_length=1)

    class Config:
        use_enum_values = True


class TriggerUpdate(BaseModel):
    """更新触发器的请求体，所有字段可选"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    trigger_type: Optional[TriggerTypeEnum] = None
    interval_value: Optional[int] = Field(None, ge=1, le=99999)
    interval_unit: Optional[IntervalUnitEnum] = None
    cron_expression: Optional[str] = Field(None, max_length=100)
    app_id: Optional[int] = None
    message: Optional[str] = Field(None, min_length=1)
    enabled: Optional[bool] = None

    class Config:
        use_enum_values = True
