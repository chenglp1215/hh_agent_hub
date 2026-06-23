from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class TriggerTypeEnum(str, Enum):
    interval = "interval"
    cron = "cron"
    wecom_bot = "wecom_bot"


class WecomChatTypeEnum(str, Enum):
    group = "group"
    user = "user"


class IntervalUnitEnum(str, Enum):
    minutes = "minutes"
    hours = "hours"
    days = "days"


class ExecutionSourceEnum(str, Enum):
    auto = "auto"
    manual = "manual"


class ExecutionStatusEnum(str, Enum):
    submitted = "submitted"
    success = "success"
    failed = "failed"


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
    notification_id: Optional[int] = None
    # wecom_bot fields
    wecom_chat_type: Optional[WecomChatTypeEnum] = None
    wecom_chat_id: Optional[str] = Field(None, max_length=100)
    wecom_user_id: Optional[str] = Field(None, max_length=100)

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
    notification_id: Optional[int] = None
    # wecom_bot fields
    wecom_chat_type: Optional[WecomChatTypeEnum] = None
    wecom_chat_id: Optional[str] = Field(None, max_length=100)
    wecom_user_id: Optional[str] = Field(None, max_length=100)

    class Config:
        use_enum_values = True


class NotificationCreate(BaseModel):
    """创建通知渠道的请求体"""
    name: str = Field(..., min_length=1, max_length=100)
    channel_type: str = Field("wecom_webhook", max_length=20)
    webhook_url: str = Field(..., min_length=1, max_length=500)


class NotificationUpdate(BaseModel):
    """更新通知渠道的请求体，所有字段可选"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    channel_type: Optional[str] = Field(None, max_length=20)
    webhook_url: Optional[str] = Field(None, min_length=1, max_length=500)
    enabled: Optional[bool] = None
