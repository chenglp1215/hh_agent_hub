from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6)
    email: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 604800


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    email: Optional[str] = None
    avatar: Optional[str] = None
    api_key: str
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True
