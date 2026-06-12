from pydantic import BaseModel, Field
from typing import Optional


class LlmConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    provider: str = Field(default="openai", pattern="^(openai|anthropic|ollama)$")
    model: str = Field(default="gpt-4o-mini", max_length=100)
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = Field(default=0.3, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=100, le=128000)
    description: Optional[str] = None


class LlmConfigUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    description: Optional[str] = None
    status: Optional[str] = None
