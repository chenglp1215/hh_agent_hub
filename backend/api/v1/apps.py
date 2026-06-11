import secrets
from fastapi import APIRouter, Depends, Query
from models.app import App
from models.workflow import Workflow
from schemas.app import AppCreate, AppUpdate
from api.deps import get_current_user
from utils.response import success, error

router = APIRouter(prefix="/apps", tags=["应用"])


def _mask_key(api_key: str) -> str:
    """将 API Key 中间部分替换为星号，用于列表展示"""
    if len(api_key) <= 8:
        return api_key[:4] + "****"
    return api_key[:4] + "****" + api_key[-4:]


@router.get("")
async def list_apps(user=Depends(get_current_user)):
    """获取应用列表"""
    apps = await App.all().prefetch_related("workflow")
    return success(data=[{
        "id": a.id,
        "name": a.name,
        "description": a.description,
        "workflow_id": a.workflow_id,
        "workflow_name": a.workflow.name if a.workflow else None,
        "api_key": _mask_key(a.api_key),
        "rate_limit": a.rate_limit,
        "enabled": a.enabled,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    } for a in apps])


@router.get("/{app_id}")
async def get_app(app_id: int, user=Depends(get_current_user)):
    """获取应用详情"""
    a = await App.get_or_none(id=app_id)
    if not a:
        return error(code=404, message="应用不存在")
    await a.fetch_related("workflow")
    return success(data={
        "id": a.id,
        "name": a.name,
        "description": a.description,
        "workflow_id": a.workflow_id,
        "workflow_name": a.workflow.name if a.workflow else None,
        "api_key": a.api_key,
        "rate_limit": a.rate_limit,
        "enabled": a.enabled,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    })


@router.post("")
async def create_app(body: AppCreate, user=Depends(get_current_user)):
    """创建新应用"""
    existing = await App.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="应用名称已存在")

    workflow = await Workflow.get_or_none(id=body.workflow_id)
    if not workflow:
        return error(code=400, message="工作流不存在")

    if workflow.status != "published":
        return error(code=400, message="只能关联已发布的工作流")

    api_key = f"ak-{secrets.token_urlsafe(24)}"
    a = await App.create(
        name=body.name,
        description=body.description,
        workflow=workflow,
        workflow_version=workflow.version,
        api_key=api_key,
        rate_limit=body.rate_limit,
        created_by=user,
    )
    return success(data={"id": a.id, "name": a.name, "api_key": api_key}, message="创建成功")


@router.put("/{app_id}")
async def update_app(app_id: int, body: AppUpdate, user=Depends(get_current_user)):
    """更新应用信息"""
    a = await App.get_or_none(id=app_id)
    if not a:
        return error(code=404, message="应用不存在")

    if body.name is not None:
        a.name = body.name
    if body.description is not None:
        a.description = body.description
    if body.workflow_id is not None:
        wf = await Workflow.get_or_none(id=body.workflow_id)
        if not wf:
            return error(code=400, message="工作流不存在")
        a.workflow = wf
    if body.rate_limit is not None:
        a.rate_limit = body.rate_limit
    if body.enabled is not None:
        a.enabled = body.enabled
    await a.save()
    return success(message="更新成功")


@router.delete("/{app_id}")
async def delete_app(app_id: int, user=Depends(get_current_user)):
    """删除应用"""
    a = await App.get_or_none(id=app_id)
    if not a:
        return error(code=404, message="应用不存在")
    await a.delete()
    return success(message="已删除")


@router.post("/{app_id}/rotate-key")
async def rotate_api_key(app_id: int, user=Depends(get_current_user)):
    """轮换应用的 API Key"""
    a = await App.get_or_none(id=app_id)
    if not a:
        return error(code=404, message="应用不存在")
    new_key = f"ak-{secrets.token_urlsafe(24)}"
    a.api_key = new_key
    await a.save()
    return success(data={"api_key": new_key}, message="密钥已轮换")


@router.get("/{app_id}/stats")
async def get_app_stats(app_id: int, user=Depends(get_current_user)):
    """获取应用统计数据（会话数和执行次数）"""
    a = await App.get_or_none(id=app_id)
    if not a:
        return error(code=404, message="应用不存在")
    from models.session import Session
    from models.workflow_trace import WorkflowTrace
    session_count = await Session.filter(app_id=app_id).count()
    trace_count = await WorkflowTrace.filter(app_id=app_id).count()
    return success(data={
        "session_count": session_count,
        "execution_count": trace_count,
    })
