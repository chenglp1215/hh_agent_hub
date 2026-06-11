from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class KBCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    kb_type: str = "file"
    config: Optional[Dict[str, Any]] = None
    embedding_model: Optional[str] = None


class KBUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    embedding_model: Optional[str] = None
