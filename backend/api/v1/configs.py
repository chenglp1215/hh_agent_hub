from fastapi import APIRouter, Depends
from loguru import logger
from models.sys_config import SysConfig
from schemas.sys_config import SysConfigUpdate
from api.deps import require_admin
from utils.response import success, error

router = APIRouter(prefix="/configs", tags=["系统配置"])


async def _publish_wecom_credentials_refresh():
    """通知 wecom-bot 重新加载凭证"""
    try:
        from core.task_queue import get_task_queue
        tq = get_task_queue()
        await tq.connect()
        await tq._redis.publish("wecom_bot:credentials_refresh", "refresh")
    except Exception as e:
        logger.warning(f"Failed to publish wecom credentials refresh: {e}")


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


@router.get("/wecom-bot-status")
async def get_wecom_bot_status(_=Depends(require_admin)):
    """获取企微机器人连接状态"""
    try:
        from core.task_queue import get_task_queue
        tq = get_task_queue()
        await tq.connect()
        status_json = await tq._redis.get("wecom_bot:status")
        if status_json:
            import json
            return success(data=json.loads(status_json))
        return success(data={
            "connected": False,
            "bot_id": "",
            "bot_name": "",
            "connected_at": "",
            "updated_at": "",
        })
    except Exception as e:
        logger.warning(f"Failed to get wecom bot status: {e}")
        return success(data={"connected": False, "bot_id": "", "bot_name": ""})


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

    # 更新 wecom 凭证时通知 wecom-bot 重连
    if key in ("wecom.bot_id", "wecom.bot_secret"):
        await _publish_wecom_credentials_refresh()

    return success(message="配置已更新")
