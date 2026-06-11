from fastapi import APIRouter, Depends, Query
from models.skill import SkillRegistry
from schemas.skill import SkillCreate, SkillUpdate
from api.deps import get_current_user, require_admin
from utils.response import success, error

router = APIRouter(prefix="/skills", tags=["Skill"])


@router.get("")
async def list_skills(
    category: str = Query(None),
    tag: str = Query(None),
    user=Depends(get_current_user),
):
    qs = SkillRegistry.all()
    if category:
        qs = qs.filter(category=category)
    skills = await qs
    if tag:
        skills = [s for s in skills if tag in (s.tags or [])]
    return success(data=[{
        "id": s.id, "name": s.name, "display_name": s.display_name,
        "description": s.description, "skill_type": s.skill_type,
        "category": s.category, "tags": s.tags, "version": s.version,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    } for s in skills])


@router.get("/{skill_id}")
async def get_skill(skill_id: int, user=Depends(get_current_user)):
    s = await SkillRegistry.get_or_none(id=skill_id)
    if not s:
        return error(code=404, message="Skill 不存在")
    return success(data={
        "id": s.id, "name": s.name, "display_name": s.display_name,
        "description": s.description, "skill_type": s.skill_type,
        "content": s.content, "category": s.category, "tags": s.tags,
        "version": s.version,
    })


@router.post("")
async def create_skill(body: SkillCreate, user=Depends(require_admin)):
    existing = await SkillRegistry.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="名称已存在")
    s = await SkillRegistry.create(
        name=body.name, display_name=body.display_name,
        description=body.description, skill_type=body.skill_type,
        content=body.content, category=body.category, tags=body.tags,
        created_by=user,
    )
    return success(data={"id": s.id, "name": s.name}, message="创建成功")


@router.put("/{skill_id}")
async def update_skill(skill_id: int, body: SkillUpdate, user=Depends(require_admin)):
    s = await SkillRegistry.get_or_none(id=skill_id)
    if not s:
        return error(code=404, message="Skill 不存在")
    for field in ["display_name", "description", "skill_type", "content", "category", "tags"]:
        val = getattr(body, field, None)
        if val is not None:
            setattr(s, field, val)
    s.version += 1
    await s.save()
    return success(message="更新成功")


@router.delete("/{skill_id}")
async def delete_skill(skill_id: int, user=Depends(require_admin)):
    s = await SkillRegistry.get_or_none(id=skill_id)
    if not s:
        return error(code=404, message="Skill 不存在")
    await s.delete()
    return success(message="已删除")
