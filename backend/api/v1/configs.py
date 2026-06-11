from fastapi import APIRouter, Depends
from models.sys_config import SysConfig
from schemas.sys_config import SysConfigUpdate
from api.deps import require_admin
from utils.response import success, error

router = APIRouter(prefix="/configs", tags=["系统配置"])


@router.get("")
async def list_configs(_=Depends(require_admin)):
    configs = await SysConfig.all()
    return success(data=[{
        "id": c.id,
        "config_key": c.config_key,
        "config_value": "***" if c.config_type == "secret" else c.config_value,
        "config_type": c.config_type,
        "description": c.description,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    } for c in configs])


@router.put("/{key}")
async def update_config(key: str, body: SysConfigUpdate, _=Depends(require_admin)):
    config = await SysConfig.get_or_none(config_key=key)
    if not config:
        return error(code=404, message="配置项不存在")
    config.config_value = body.config_value
    if body.config_type:
        config.config_type = body.config_type
    if body.description is not None:
        config.description = body.description
    await config.save()
    return success(message="配置已更新")
