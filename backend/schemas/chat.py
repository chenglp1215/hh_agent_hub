from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    """Chat API 请求体"""
    app_id: int
    session_id: Optional[str] = None
    message: str = Field(..., min_length=1)
    stream: bool = False
