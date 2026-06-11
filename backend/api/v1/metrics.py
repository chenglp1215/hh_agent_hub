from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user, require_admin
from models.workflow_trace import WorkflowTrace
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
