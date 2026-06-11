import json
import os

from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user
from models.workflow_trace import WorkflowTrace
from utils.response import success, error

router = APIRouter(prefix="/traces", tags=["执行追踪"])


@router.get("")
async def list_traces(
    status: str = Query(None),
    workflow_id: int = Query(None),
    limit: int = Query(20, le=100),
    user=Depends(get_current_user),
):
    qs = WorkflowTrace.all().order_by("-created_at")
    if status:
        qs = qs.filter(status=status)
    if workflow_id:
        qs = qs.filter(workflow_id=workflow_id)
    traces = await qs.limit(limit)
    return success(data=[{
        "id": t.id, "execution_id": t.execution_id,
        "workflow_id": t.workflow_id, "app_id": t.app_id,
        "status": t.status, "agent_count": t.agent_count,
        "total_duration_ms": t.total_duration_ms,
        "error_agent": t.error_agent, "error_summary": t.error_summary,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    } for t in traces])


@router.get("/{execution_id}")
async def get_trace_detail(execution_id: str, user=Depends(get_current_user)):
    t = await WorkflowTrace.get_or_none(execution_id=execution_id)
    if not t:
        return error(code=404, message="追踪记录不存在")
    trace_data = {}
    if t.trace_file_path and os.path.exists(t.trace_file_path):
        with open(t.trace_file_path, "r", encoding="utf-8") as f:
            trace_data = json.load(f)
    return success(data={
        "metadata": {
            "id": t.id, "execution_id": t.execution_id,
            "workflow_id": t.workflow_id, "app_id": t.app_id,
            "status": t.status, "agent_count": t.agent_count,
            "total_duration_ms": t.total_duration_ms,
            "error_agent": t.error_agent, "error_summary": t.error_summary,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        },
        "trace_tree": trace_data,
    })
