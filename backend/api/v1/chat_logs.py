"""ChatLog 查询 API — 查看所有 Chat 交互记录"""

from fastapi import APIRouter, Request, Query
from models.chat_log import ChatLog
from utils.response import success, error

router = APIRouter(prefix="/chat-logs", tags=["对话日志"])


@router.get("")
async def list_chat_logs(
    request: Request,
    app_id: int = Query(None, description="按应用筛选"),
    session_id: str = Query(None, description="按会话筛选"),
    status: str = Query(None, description="按状态筛选: success/error"),
    keyword: str = Query(None, description="按关键词搜索 user_input"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    """查询 Chat 交互日志列表"""
    filters = {}
    if app_id:
        filters["app_id"] = app_id
    if session_id:
        filters["session_id"] = session_id
    if status:
        filters["status"] = status

    query = ChatLog.filter(**filters)

    if keyword:
        query = query.filter(user_input__icontains=keyword)

    total = await query.count()
    items = (
        await query
        .order_by("-created_at")
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return success(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [{
            "id": log.id,
            "app_id": log.app_id,
            "session_id": log.session_id,
            "task_id": log.task_id,
            "user_input": log.user_input,
            "final_answer": log.final_answer,
            "duration_ms": log.duration_ms,
            "status": log.status,
            "error_message": log.error_message,
            "agent_count": log.agent_count,
            "trace_summary": log.trace_summary,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        } for log in items],
    })


@router.get("/{log_id}")
async def get_chat_log(log_id: int, request: Request):
    """获取单条 ChatLog 详情"""
    log = await ChatLog.get_or_none(id=log_id)
    if not log:
        return error(code=404, message="日志不存在")
    return success(data={
        "id": log.id,
        "app_id": log.app_id,
        "session_id": log.session_id,
        "task_id": log.task_id,
        "user_input": log.user_input,
        "final_answer": log.final_answer,
        "duration_ms": log.duration_ms,
        "status": log.status,
        "error_message": log.error_message,
        "agent_count": log.agent_count,
        "trace_summary": log.trace_summary,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    })
