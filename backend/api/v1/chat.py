import uuid
import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from models.app import App
from models.session import Session
from schemas.chat import ChatRequest
from utils.response import success, error
from utils.sse import sse_event
from core.session_manager import session_manager
from core.task_queue import get_task_queue
from api.deps import get_current_user
from loguru import logger

router = APIRouter(prefix="/chat", tags=["对话"])


@router.post("")
async def chat(req: ChatRequest, request: Request):
    """Chat API 入口 — 将任务提交到 worker 队列

    支持流式（SSE）和非流式两种响应模式。
    通过 ApiKeyMiddleware 完成应用认证，也可以通过 app_id 直接查找应用。
    """
    app = getattr(request.state, "app", None)
    if not app:
        app = await App.get_or_none(id=req.app_id, enabled=True)
    if not app:
        return error(code=400, message="应用不存在或已禁用")

    # 1. 获取/创建 session + workspace
    session_id = req.session_id or str(uuid.uuid4())
    session = await Session.get_or_none(id=session_id)

    if not session:
        workspace_path = await session_manager.create_workspace(session_id)
        session = await Session.create(
            id=session_id,
            app=app,
            user_id="",
            messages=[],
            workspace_path=workspace_path,
            expired_at=datetime.now() + timedelta(hours=1),
        )

    # 2. 提交任务到 worker 队列
    task_queue = get_task_queue()
    task_id = await task_queue.enqueue(
        app_id=app.id,
        session_id=session_id,
        message=req.message,
        stream=req.stream,
    )

    # 3. 根据 stream 模式选择响应方式
    if req.stream:
        return StreamingResponse(
            _stream_response(task_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    return await _poll_response(task_id)


async def _poll_response(task_id: str):
    """非流式：轮询等待 worker 结果"""
    task_queue = get_task_queue()
    result = await task_queue.get_result(task_id, timeout=600)

    if result is None:
        return error(code=504, message="任务执行超时")

    if "error" in result and not result.get("final_answer"):
        return error(code=500, message=result["error"])

    return success(data={
        "session_id": result.get("session_id", ""),
        "message": result.get("final_answer", ""),
        "intermediate_results": result.get("intermediate_results", {}),
        "duration_ms": result.get("duration_ms", 0),
        "trace": result.get("trace", []),
    })


async def _stream_response(task_id: str):
    """流式：通过 Redis pub/sub 订阅 worker 事件并转发为 SSE"""
    task_queue = get_task_queue()
    try:
        async for event in task_queue.subscribe_events(task_id):
            event_type = event.pop("type", "unknown")
            yield await sse_event(event_type, event)
            if event_type in ("done", "error"):
                return
    except Exception as e:
        logger.error(f"SSE stream error for task {task_id}: {e}")
        yield await sse_event("error", {"message": str(e)})


from api.deps import get_current_user

@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request, user=Depends(get_current_user)):
    """获取会话历史消息"""
    session = await Session.get_or_none(id=session_id)
    if not session:
        return error(code=404, message="会话不存在")
    return success(data={
        "session_id": session.id,
        "app_id": session.app_id,
        "messages": session.messages,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    })


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request, user=Depends(get_current_user)):
    """清除会话及其 workspace"""
    session = await Session.get_or_none(id=session_id)
    if not session:
        return error(code=404, message="会话不存在")
    await session_manager.cleanup_workspace(session_id)
    await session.delete()
    return success(message="会话已清除")
