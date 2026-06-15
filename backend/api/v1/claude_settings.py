import json
from fastapi import APIRouter, Depends, Query
from models.claude_settings import ClaudeSettingsRegistry
from schemas.claude_settings import ClaudeSettingsCreate, ClaudeSettingsUpdate
from api.deps import get_current_user, require_admin
from utils.response import success, error

router = APIRouter(prefix="/claude-settings", tags=["Claude Settings"])


@router.get("")
async def list_settings(
    search: str = Query(None),
    user=Depends(get_current_user),
):
    qs = ClaudeSettingsRegistry.all()
    settings = await qs

    if search:
        q = search.lower()
        settings = [s for s in settings if q in (s.name + (s.display_name or "")).lower()]

    return success(data=[{
        "id": s.id, "name": s.name, "display_name": s.display_name,
        "description": s.description, "model": s.model,
        "max_turns": s.max_turns, "permission_mode": s.permission_mode,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    } for s in settings])


@router.get("/{settings_id}")
async def get_settings(settings_id: int, user=Depends(get_current_user)):
    s = await ClaudeSettingsRegistry.get_or_none(id=settings_id)
    if not s:
        return error(code=404, message="Claude 配置不存在")
    return success(data={
        "id": s.id, "name": s.name, "display_name": s.display_name,
        "description": s.description, "model": s.model,
        "max_turns": s.max_turns, "permission_mode": s.permission_mode,
        "settings_json": s.settings_json, "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    })


@router.post("")
async def create_settings(body: ClaudeSettingsCreate, user=Depends(require_admin)):
    existing = await ClaudeSettingsRegistry.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="名称已存在")

    if body.settings_json and body.settings_json.strip():
        try:
            json.loads(body.settings_json)
        except json.JSONDecodeError:
            return error(code=400, message="settings_json 格式错误，请输入合法的 JSON")

    s = await ClaudeSettingsRegistry.create(
        name=body.name, display_name=body.display_name,
        description=body.description, model=body.model or "claude-sonnet-4-6",
        max_turns=body.max_turns or 25,
        permission_mode=body.permission_mode or "acceptEdits",
        settings_json=body.settings_json,
        created_by=user,
    )
    return success(data={"id": s.id, "name": s.name}, message="创建成功")


@router.put("/{settings_id}")
async def update_settings(settings_id: int, body: ClaudeSettingsUpdate, user=Depends(require_admin)):
    s = await ClaudeSettingsRegistry.get_or_none(id=settings_id)
    if not s:
        return error(code=404, message="Claude 配置不存在")

    if body.settings_json is not None and body.settings_json.strip():
        try:
            json.loads(body.settings_json)
        except json.JSONDecodeError:
            return error(code=400, message="settings_json 格式错误，请输入合法的 JSON")

    updatable = ["display_name", "description", "model", "max_turns",
                  "permission_mode", "settings_json", "status"]
    for field in updatable:
        val = getattr(body, field, None)
        if val is not None:
            setattr(s, field, val)

    await s.save()
    return success(message="更新成功")


@router.delete("/{settings_id}")
async def delete_settings(settings_id: int, user=Depends(require_admin)):
    s = await ClaudeSettingsRegistry.get_or_none(id=settings_id)
    if not s:
        return error(code=404, message="Claude 配置不存在")
    await s.delete()
    return success(message="已删除")
