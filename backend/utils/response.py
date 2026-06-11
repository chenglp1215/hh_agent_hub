from typing import Any, Optional
from pydantic import BaseModel


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None


def success(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def error(code: int = -1, message: str = "error", data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data}
