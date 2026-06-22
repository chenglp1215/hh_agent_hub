from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user, require_admin
from models.workflow_trace import WorkflowTrace
from models.agent import Agent
from models.workflow import Workflow
from models.app import App
from models.mcp_server import McpServerRegistry
from models.knowledge_base import KnowledgeBase
from models.skill import SkillRegistry
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
    mcp_count = await McpServerRegistry.all().count()
    kb_count = await KnowledgeBase.all().count()
    skill_count = await SkillRegistry.all().count()

    # Today's executions
    from datetime import datetime, timedelta
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    traces = await WorkflowTrace.all()
    today_executions = sum(1 for t in traces if t.created_at and t.created_at >= today_start)

    # MCP online count
    mcp_online = sum(1 for _ in [])  # placeholder — actual check requires connection testing

    # Recent traces (last 10)
    recent_traces = sorted(traces, key=lambda t: t.created_at or datetime.min, reverse=True)[:10]

    return success(data={
        "agents": agent_count,
        "workflows": workflow_count,
        "apps": app_count,
        "today_executions": today_executions,
        "mcp_online": mcp_online,
        "kb_count": kb_count,
        "skill_count": skill_count,
        "recent_traces": [
            {
                "id": t.id,
                "execution_id": t.execution_id,
                "status": t.status,
                "total_duration_ms": t.total_duration_ms,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in recent_traces
        ],
    })
