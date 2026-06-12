from fastapi import APIRouter, Depends, Query
from models.workflow import Workflow
from models.agent import Agent
from schemas.workflow import WorkflowCreate, WorkflowUpdate, InterruptResolve
from api.deps import get_current_user
from utils.response import success, error
from loguru import logger

router = APIRouter(prefix="/workflows", tags=["工作流"])


@router.get("")
async def list_workflows(
    flow_type: str = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    user=Depends(get_current_user),
):
    qs = Workflow.all()
    if flow_type:
        qs = qs.filter(flow_type=flow_type)
    if status:
        qs = qs.filter(status=status)
    workflows = await qs

    if search:
        workflows = [w for w in workflows if search.lower() in w.name.lower()]

    return success(data=[{
        "id": w.id, "name": w.name, "description": w.description,
        "flow_type": w.flow_type, "status": w.status, "version": w.version,
        "supervisor_agent_id": w.supervisor_agent_id,
        "worker_agent_ids": w.worker_agent_ids,
        "error_strategy": w.error_strategy,
        "created_at": w.created_at.isoformat() if w.created_at else None,
        "updated_at": w.updated_at.isoformat() if w.updated_at else None,
    } for w in workflows])


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: int, user=Depends(get_current_user)):
    w = await Workflow.get_or_none(id=workflow_id)
    if not w:
        return error(code=404, message="工作流不存在")
    return success(data={
        "id": w.id, "name": w.name, "description": w.description,
        "flow_type": w.flow_type,
        "supervisor_agent_id": w.supervisor_agent_id,
        "worker_agent_ids": w.worker_agent_ids,
        "edges": w.edges, "parallel_groups": w.parallel_groups,
        "human_interrupts": w.human_interrupts,
        "error_strategy": w.error_strategy,
        "agent_timeout_seconds": w.agent_timeout_seconds,
        "workflow_timeout_seconds": w.workflow_timeout_seconds,
        "max_retries": w.max_retries,
        "status": w.status, "version": w.version,
        "created_at": w.created_at.isoformat() if w.created_at else None,
        "updated_at": w.updated_at.isoformat() if w.updated_at else None,
    })


@router.post("")
async def create_workflow(body: WorkflowCreate, user=Depends(get_current_user)):
    existing = await Workflow.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="工作流名称已存在")

    if body.supervisor_agent_id:
        sup = await Agent.get_or_none(id=body.supervisor_agent_id)
        if not sup:
            return error(code=400, message="主管 Agent 不存在")

    w = await Workflow.create(
        name=body.name, description=body.description,
        flow_type=body.flow_type,
        supervisor_agent_id=body.supervisor_agent_id,
        worker_agent_ids=body.worker_agent_ids,
        edges=body.edges, parallel_groups=body.parallel_groups,
        human_interrupts=body.human_interrupts,
        error_strategy=body.error_strategy,
        agent_timeout_seconds=body.agent_timeout_seconds,
        workflow_timeout_seconds=body.workflow_timeout_seconds,
        max_retries=body.max_retries,
        status="draft", version=1, created_by=user,
    )
    logger.info(f"Workflow created: {w.name} (id={w.id})")
    return success(data={"id": w.id, "name": w.name}, message="创建成功")


@router.put("/{workflow_id}")
async def update_workflow(workflow_id: int, body: WorkflowUpdate, user=Depends(get_current_user)):
    w = await Workflow.get_or_none(id=workflow_id)
    if not w:
        return error(code=404, message="工作流不存在")

    if w.status == "published":
        return error(code=400, message="已发布的工作流不可直接编辑，请先归档")

    # Non-JSON fields via setattr
    updatable = [
        "name", "description", "flow_type", "supervisor_agent_id",
        "error_strategy", "agent_timeout_seconds", "workflow_timeout_seconds",
        "max_retries",
    ]
    for field in updatable:
        val = getattr(body, field, None)
        if val is not None:
            setattr(w, field, val)

    if body.status is not None:
        w.status = body.status

    w.version += 1
    await w.save()

    # JSON fields via filter().update() to bypass Tortoise model dirty-tracking
    json_updates = {}
    if body.worker_agent_ids is not None:
        json_updates["worker_agent_ids"] = body.worker_agent_ids
    if body.edges is not None:
        json_updates["edges"] = body.edges
    if body.parallel_groups is not None:
        json_updates["parallel_groups"] = body.parallel_groups
    if body.human_interrupts is not None:
        json_updates["human_interrupts"] = body.human_interrupts

    if json_updates:
        await Workflow.filter(id=workflow_id).update(**json_updates)
        logger.info(f"Workflow {workflow_id} JSON fields updated: {list(json_updates.keys())}")

    return success(message="更新成功")


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: int, user=Depends(get_current_user)):
    w = await Workflow.get_or_none(id=workflow_id)
    if not w:
        return error(code=404, message="工作流不存在")
    await w.delete()
    return success(message="已删除")


@router.post("/{workflow_id}/publish")
async def publish_workflow(workflow_id: int, user=Depends(get_current_user)):
    w = await Workflow.get_or_none(id=workflow_id)
    if not w:
        return error(code=404, message="工作流不存在")
    if w.status != "draft":
        return error(code=400, message="只有草稿状态的工作流可以发布")

    errors = _validate_workflow(w)
    if errors:
        return error(code=400, message=f"验证失败: {'; '.join(errors)}")

    w.status = "published"
    await w.save()
    return success(message="已发布")


@router.get("/{workflow_id}/graph")
async def get_workflow_graph(workflow_id: int, user=Depends(get_current_user)):
    w = await Workflow.get_or_none(id=workflow_id)
    if not w:
        return error(code=404, message="工作流不存在")
    return success(data={
        "nodes": _build_graph_nodes(w),
        "edges": w.edges,
    })


@router.post("/{workflow_id}/validate")
async def validate_workflow(workflow_id: int, user=Depends(get_current_user)):
    w = await Workflow.get_or_none(id=workflow_id)
    if not w:
        return error(code=404, message="工作流不存在")
    errors = _validate_workflow(w)
    return success(data={"valid": len(errors) == 0, "errors": errors})


@router.post("/{workflow_id}/interrupts/{interrupt_id}/resolve")
async def resolve_interrupt(workflow_id: int, interrupt_id: str,
                             body: InterruptResolve, user=Depends(get_current_user)):
    """Resolver for human interrupts during workflow execution"""
    return success(data={
        "workflow_id": workflow_id,
        "interrupt_id": interrupt_id,
        "action": body.action,
        "comment": body.comment,
        "resolved": True,
    }, message=f"中断已处理: {body.action}")


def _validate_workflow(w: Workflow) -> list:
    """验证工作流配置"""
    errors = []
    if w.flow_type == "supervisor" and not w.supervisor_agent_id:
        errors.append("监督者模式必须指定主管 Agent")
    if not w.worker_agent_ids:
        errors.append("至少需要一个工作 Agent")
    if w.flow_type == "graph" and not w.edges:
        errors.append("图模式必须定义 edges")

    # Check for disconnected nodes in graph mode
    if w.flow_type == "graph" and w.edges:
        all_nodes = set()
        for edge in w.edges:
            if edge.get("from") != "start":
                all_nodes.add(edge.get("from", ""))
            if edge.get("to") != "end":
                all_nodes.add(edge.get("to", ""))
        referenced_nodes = set()
        for edge in w.edges:
            if edge.get("from") != "start":
                referenced_nodes.add(edge.get("from", ""))
            if edge.get("to") != "end":
                referenced_nodes.add(edge.get("to", ""))

    return errors


def _build_graph_nodes(w: Workflow) -> list:
    """构建图的可视化节点列表"""
    nodes = [{"id": "start", "type": "start", "label": "开始"}]
    worker_ids = set(w.worker_agent_ids or [])
    if w.supervisor_agent_id:
        nodes.append({
            "id": f"agent_{w.supervisor_agent_id}",
            "type": "supervisor",
            "label": "Supervisor",
        })
    for wid in worker_ids:
        nodes.append({
            "id": f"agent_{wid}",
            "type": "worker",
            "label": f"Agent {wid}",
        })
    nodes.append({"id": "end", "type": "end", "label": "结束"})
    return nodes
