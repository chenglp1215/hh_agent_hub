from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class ReasonixSettingsCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    model: str = "deepseek-v4-pro"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.0
    max_turns: int = 25
    reasoning_language: str = "zh"
    auto_plan: str = "off"
    compact_ratio: float = 0.8
    extra_json: Optional[Dict[str, Any]] = None


class ReasonixSettingsUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    max_turns: Optional[int] = None
    reasoning_language: Optional[str] = None
    auto_plan: Optional[str] = None
    compact_ratio: Optional[float] = None
    extra_json: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
