from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user, require_admin
from models.workflow_trace import WorkflowTrace
from models.agent import Agent
from models.workflow import Workflow
from models.app import App
from models.mcp_server import McpServerRegistry
from models.knowledge_base import KnowledgeBase
from models.skill import SkillRegistry
from models.chat_log import ChatLog
from utils.response import success

router = APIRouter(prefix="/system/metrics", tags=["监控指标"])


@router.get("")
async def get_metrics(user=Depends(require_admin)):
    all_traces = await WorkflowTrace.all()

    total = len(all_traces)
    success_count = sum(1 for t in all_traces if t.status == "success")
    failed_count = sum(1 for t in all_traces if t.status == "failed")

    durations = [t.total_duration_ms for t in all_traces if t.total_duration_ms is not None]
    durations.sort()

    p95_idx = int(len(durations) * 0.95) if durations else 0
    p50_idx = int(len(durations) * 0.50) if durations else 0

    # Agent failure stats
    agent_failures = {}
    for t in all_traces:
        if t.error_agent:
            agent_failures[t.error_agent] = agent_failures.get(t.error_agent, 0) + 1

    top_failures = sorted(agent_failures.items(), key=lambda x: x[1], reverse=True)[:5]

    return success(data={
        "workflows": {
            "total_executions": total,
            "success_rate": round(success_count / total, 2) if total > 0 else 0,
            "p50_duration_ms": durations[p50_idx] if durations else 0,
            "p95_duration_ms": durations[p95_idx] if durations else 0,
            "failed": failed_count,
        },
        "agents_top_failures": [
            {"agent": name, "failures": count}
            for name, count in top_failures
        ],
    })


# Dashboard stats — accessible to all authenticated users
dashboard_router = APIRouter(prefix="/dashboard", tags=["主控台"])


@dashboard_router.get("/stats")
async def get_dashboard_stats(user=Depends(get_current_user)):
    """Aggregated counts for the main dashboard."""
    agent_count = await Agent.all().count()
    workflow_count = await Workflow.all().count()
    app_count = await App.all().count()
    kb_count = await KnowledgeBase.all().count()
    skill_count = await SkillRegistry.all().count()

    # MCP server counts — 简单用 status 判断在线
    mcp_total = await McpServerRegistry.all().count()
    mcp_online = await McpServerRegistry.filter(status="active").count()

    # Today's executions (北京时间零点)
    from datetime import datetime, timedelta, timezone
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz).replace(tzinfo=None)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_executions = await ChatLog.filter(created_at__gte=today_start).count()

    # 今日 token 消耗（总计 + 按模型分组）
    today_logs = await ChatLog.filter(
        created_at__gte=today_start, total_tokens__gt=0
    ).all()
    today_total_tokens = sum(t.total_tokens or 0 for t in today_logs)
    today_prompt_tokens = sum(t.prompt_tokens or 0 for t in today_logs)
    today_completion_tokens = sum(t.completion_tokens or 0 for t in today_logs)

    # 按模型分组统计（优先使用 token_by_model JSON 字段，兼容旧 model_name 字段）
    token_by_model: dict = {}
    for t in today_logs:
        if t.token_by_model:
            for model, usage in t.token_by_model.items():
                if model not in token_by_model:
                    token_by_model[model] = {"prompt": 0, "completion": 0, "total": 0}
                token_by_model[model]["prompt"] += usage.get("prompt", 0)
                token_by_model[model]["completion"] += usage.get("completion", 0)
                token_by_model[model]["total"] += usage.get("total", 0)
        else:
            model = t.model_name or "unknown"
            if model not in token_by_model:
                token_by_model[model] = {"prompt": 0, "completion": 0, "total": 0}
            token_by_model[model]["prompt"] += t.prompt_tokens or 0
            token_by_model[model]["completion"] += t.completion_tokens or 0
            token_by_model[model]["total"] += t.total_tokens or 0

    # Recent chat logs (last 10)
    recent_logs = await ChatLog.all().order_by('-created_at').limit(10)

    # Task queue status
    queue_depth = 0
    active_tasks = 0
    try:
        from core.task_queue import get_task_queue
        tq = get_task_queue()
        await tq.connect()
        queue_depth = await tq._redis.llen("workflow:queue")
        # 清理已完成/已中断的任务
        task_ids = await tq._redis.smembers("workflow:active_tasks")
        if task_ids:
            logged = set(await ChatLog.filter(task_id__in=list(task_ids)).values_list("task_id", flat=True))
            for tid in task_ids:
                if tid in logged or await tq._redis.exists(f"workflow:result:{tid}"):
                    await tq._redis.srem("workflow:active_tasks", tid)
        active_tasks = await tq._redis.scard("workflow:active_tasks")
    except Exception:
        pass

    # Worker 状态
    worker_count = 0
    try:
        from core.task_queue import get_task_queue
        tq = get_task_queue()
        await tq.connect()
        worker_keys = await tq._redis.keys("worker:heartbeat:*")
        worker_count = len(worker_keys)
    except Exception:
        pass

    return success(data={
        "agents": agent_count,
        "workflows": workflow_count,
        "apps": app_count,
        "today_executions": today_executions,
        "mcp_online": mcp_online,
        "mcp_total": mcp_total,
        "kb_count": kb_count,
        "skill_count": skill_count,
        "queue_depth": queue_depth,
        "active_tasks": active_tasks,
        "worker_count": worker_count,
        "today_tokens": {
            "prompt": today_prompt_tokens,
            "completion": today_completion_tokens,
            "total": today_total_tokens,
        },
        "token_by_model": token_by_model,
        "recent_logs": [
            {
                "id": log.id,
                "session_id": log.session_id,
                "app_id": log.app_id,
                "user_input": (log.user_input or "")[:100],
                "final_answer": (log.final_answer or "")[:100],
                "status": log.status,
                "duration_ms": log.duration_ms,
                "total_tokens": log.total_tokens,
                "model_name": log.model_name,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in recent_logs
        ],
    })
