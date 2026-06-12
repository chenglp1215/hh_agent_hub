from typing import Any, Optional
from pydantic import BaseModel
from fastapi.responses import JSONResponse


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None


def success(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def error(code: int = -1, message: str = "error", data: Any = None):
    return JSONResponse(
        status_code=code if code >= 100 else 400,
        content={"code": code, "message": message, "data": data},
    )
