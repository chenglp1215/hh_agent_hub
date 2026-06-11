from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any


class McpServerCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    base_url: str = Field(..., max_length=500)
    headers: Optional[Dict[str, str]] = {}
    timeout: int = 30


class McpServerUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    base_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout: Optional[int] = None
