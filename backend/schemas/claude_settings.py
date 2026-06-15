from pydantic import BaseModel, Field
from typing import Optional


class ClaudeSettingsCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    model: str = "claude-sonnet-4-6"
    max_turns: int = 25
    permission_mode: str = "acceptEdits"
    settings_json: Optional[str] = None


class ClaudeSettingsUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    max_turns: Optional[int] = None
    permission_mode: Optional[str] = None
    settings_json: Optional[str] = None
    status: Optional[str] = None
