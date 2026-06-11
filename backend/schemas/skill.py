from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    skill_type: str = "prompt"
    content: Optional[Dict[str, Any]] = None
    category: Optional[str] = None
    tags: List[str] = []


class SkillUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    skill_type: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
