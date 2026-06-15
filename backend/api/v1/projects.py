from fastapi import APIRouter, Depends, Query
from models.project_registry import ProjectRegistry
from schemas.project_registry import ProjectRegistryCreate, ProjectRegistryUpdate
from api.deps import get_current_user, require_admin
from utils.response import success, error

router = APIRouter(prefix="/projects", tags=["Project Registry"])


@router.get("")
async def list_projects(
    status: str = Query(None),
    search: str = Query(None),
    user=Depends(get_current_user),
):
    qs = ProjectRegistry.all()
    if status:
        qs = qs.filter(status=status)
    projects = await qs

    if search:
        q = search.lower()
        projects = [p for p in projects if q in (p.name + (p.display_name or "") + p.git_repo_url).lower()]

    return success(data=[{
        "id": p.id, "name": p.name, "display_name": p.display_name,
        "description": p.description, "git_repo_url": p.git_repo_url,
        "git_branch": p.git_branch,
        "clone_path": p.clone_path, "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    } for p in projects])


@router.get("/{project_id}")
async def get_project(project_id: int, user=Depends(get_current_user)):
    p = await ProjectRegistry.get_or_none(id=project_id)
    if not p:
        return error(code=404, message="项目不存在")
    return success(data={
        "id": p.id, "name": p.name, "display_name": p.display_name,
        "description": p.description, "git_repo_url": p.git_repo_url,
        "git_branch": p.git_branch,
        "git_auth_username": p.git_auth_username,
        "git_auth_token": p.git_auth_token,
        "clone_path": p.clone_path, "system_prompt": p.system_prompt,
        "fix_timeout_minutes": p.fix_timeout_minutes, "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    })


@router.post("")
async def create_project(body: ProjectRegistryCreate, user=Depends(require_admin)):
    existing = await ProjectRegistry.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="名称已存在")
    if not body.git_repo_url.strip():
        return error(code=400, message="Git 仓库地址不能为空")

    p = await ProjectRegistry.create(
        name=body.name, display_name=body.display_name,
        description=body.description, git_repo_url=body.git_repo_url.rstrip("/"),
        git_branch=body.git_branch or "main",
        git_auth_username=body.git_auth_username,
        git_auth_token=body.git_auth_token,
        clone_path=body.clone_path, system_prompt=body.system_prompt,
        fix_timeout_minutes=body.fix_timeout_minutes or 30,
        created_by=user,
    )
    return success(data={"id": p.id, "name": p.name}, message="创建成功")


@router.put("/{project_id}")
async def update_project(project_id: int, body: ProjectRegistryUpdate, user=Depends(require_admin)):
    p = await ProjectRegistry.get_or_none(id=project_id)
    if not p:
        return error(code=404, message="项目不存在")

    updatable = ["display_name", "description", "git_repo_url", "git_branch",
                  "git_auth_username", "git_auth_token", "clone_path",
                  "system_prompt", "fix_timeout_minutes", "status"]
    for field in updatable:
        val = getattr(body, field, None)
        if val is not None:
            if field == "git_repo_url":
                val = val.rstrip("/")
            setattr(p, field, val)

    await p.save()
    return success(message="更新成功")


@router.delete("/{project_id}")
async def delete_project(project_id: int, user=Depends(require_admin)):
    p = await ProjectRegistry.get_or_none(id=project_id)
    if not p:
        return error(code=404, message="项目不存在")
    await p.delete()
    return success(message="已删除")
