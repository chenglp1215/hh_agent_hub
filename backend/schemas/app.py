from pydantic import BaseModel, Field
from typing import Optional


class AppCreate(BaseModel):
    """创建应用的请求体"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    workflow_id: int
    rate_limit: int = 60


class AppUpdate(BaseModel):
    """更新应用的请求体，所有字段可选"""
    name: Optional[str] = None
    description: Optional[str] = None
    workflow_id: Optional[int] = None
    rate_limit: Optional[int] = None
    enabled: Optional[bool] = None
