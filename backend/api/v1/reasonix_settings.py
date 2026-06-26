from fastapi import APIRouter, Depends, Query
from models.reasonix_settings import ReasonixSettingsRegistry
from schemas.reasonix_settings import ReasonixSettingsCreate, ReasonixSettingsUpdate
from api.deps import get_current_user, require_admin
from utils.response import success, error

router = APIRouter(prefix="/reasonix-settings", tags=["Reasonix Settings"])


@router.get("")
async def list_settings(
    search: str = Query(None),
    user=Depends(get_current_user),
):
    qs = ReasonixSettingsRegistry.all()
    settings = await qs

    if search:
        q = search.lower()
        settings = [s for s in settings if q in (s.name + (s.display_name or "")).lower()]

    return success(data=[{
        "id": s.id, "name": s.name, "display_name": s.display_name,
        "description": s.description, "model": s.model,
        "temperature": s.temperature, "max_turns": s.max_turns,
        "reasoning_language": s.reasoning_language, "auto_plan": s.auto_plan,
        "compact_ratio": s.compact_ratio,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    } for s in settings])


@router.get("/{settings_id}")
async def get_settings(settings_id: int, user=Depends(get_current_user)):
    s = await ReasonixSettingsRegistry.get_or_none(id=settings_id)
    if not s:
        return error(code=404, message="Reasonix 配置不存在")
    return success(data={
        "id": s.id, "name": s.name, "display_name": s.display_name,
        "description": s.description, "model": s.model,
        "api_key": s.api_key, "temperature": s.temperature,
        "max_turns": s.max_turns, "reasoning_language": s.reasoning_language,
        "auto_plan": s.auto_plan, "compact_ratio": s.compact_ratio,
        "extra_json": s.extra_json, "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    })


@router.post("")
async def create_settings(body: ReasonixSettingsCreate, user=Depends(require_admin)):
    existing = await ReasonixSettingsRegistry.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="名称已存在")

    s = await ReasonixSettingsRegistry.create(
        name=body.name, display_name=body.display_name,
        description=body.description, model=body.model or "deepseek-v4-pro",
        api_key=body.api_key, temperature=body.temperature or 0.0,
        max_turns=body.max_turns or 25,
        reasoning_language=body.reasoning_language or "zh",
        auto_plan=body.auto_plan or "off",
        compact_ratio=body.compact_ratio or 0.8,
        extra_json=body.extra_json,
        created_by=user,
    )
    return success(data={"id": s.id, "name": s.name}, message="创建成功")


@router.put("/{settings_id}")
async def update_settings(settings_id: int, body: ReasonixSettingsUpdate, user=Depends(require_admin)):
    s = await ReasonixSettingsRegistry.get_or_none(id=settings_id)
    if not s:
        return error(code=404, message="Reasonix 配置不存在")

    updatable = ["display_name", "description", "model", "api_key",
                 "temperature", "max_turns", "reasoning_language",
                 "auto_plan", "compact_ratio", "extra_json", "status"]
    for field in updatable:
        val = getattr(body, field, None)
        if val is not None:
            setattr(s, field, val)

    await s.save()
    return success(message="更新成功")


@router.delete("/{settings_id}")
async def delete_settings(settings_id: int, user=Depends(require_admin)):
    s = await ReasonixSettingsRegistry.get_or_none(id=settings_id)
    if not s:
        return error(code=404, message="Reasonix 配置不存在")
    await s.delete()
    return success(message="已删除")
