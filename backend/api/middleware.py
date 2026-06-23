from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from models.app import App


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # 精确匹配 /api/v1/chat 及其子路径，排除 sessions 和 chat-logs
        if path == "/api/v1/chat" or (path.startswith("/api/v1/chat/") and not path.startswith("/api/v1/chat/sessions")):
            api_key = request.headers.get("X-API-Key", "")
            if not api_key:
                return JSONResponse(
                    status_code=401,
                    content={"code": 401, "message": "未提供 API Key"},
                )

            app = await App.get_or_none(api_key=api_key, enabled=True)
            if not app:
                return JSONResponse(
                    status_code=401,
                    content={"code": 401, "message": "无效的 API Key"},
                )

            request.state.app = app
            request.state.auth_type = "api_key"
        return await call_next(request)
