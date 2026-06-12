from fastapi import APIRouter, Depends
from models.llm_config import LlmConfig
from schemas.llm_config import LlmConfigCreate, LlmConfigUpdate
from api.deps import get_current_user
from models.user import User
from utils.response import success, error

router = APIRouter(prefix="/llm-configs", tags=["LLM配置"])


@router.get("")
async def list_configs(user: User = Depends(get_current_user)):
    configs = await LlmConfig.all()
    return success(data=[{
        "id": c.id, "name": c.name, "provider": c.provider, "model": c.model,
        "api_key": c.api_key, "base_url": c.base_url,
        "temperature": c.temperature, "max_tokens": c.max_tokens,
        "description": c.description, "status": c.status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    } for c in configs])


@router.post("")
async def create_config(body: LlmConfigCreate, user: User = Depends(get_current_user)):
    existing = await LlmConfig.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="名称已存在")
    c = await LlmConfig.create(
        name=body.name, provider=body.provider, model=body.model,
        api_key=body.api_key, base_url=body.base_url,
        temperature=body.temperature, max_tokens=body.max_tokens,
        description=body.description,
    )
    return success(data={"id": c.id, "name": c.name}, message="创建成功")


@router.put("/{config_id}")
async def update_config(config_id: int, body: LlmConfigUpdate, user: User = Depends(get_current_user)):
    c = await LlmConfig.get_or_none(id=config_id)
    if not c:
        return error(code=404, message="LLM 配置不存在")
    for field in ["name", "provider", "model", "api_key", "base_url",
                   "temperature", "max_tokens", "description", "status"]:
        val = getattr(body, field, None)
        if val is not None:
            setattr(c, field, val)
    await c.save()
    return success(message="更新成功")


@router.delete("/{config_id}")
async def delete_config(config_id: int, user: User = Depends(get_current_user)):
    c = await LlmConfig.get_or_none(id=config_id)
    if not c:
        return error(code=404, message="LLM 配置不存在")
    await c.delete()
    return success(message="已删除")
