"""通知渠道 CRUD API"""

from datetime import datetime
from fastapi import APIRouter, Depends
from models.trigger import NotificationChannel
from schemas.trigger import NotificationCreate, NotificationUpdate
from api.deps import get_current_user
from utils.response import success, error

router = APIRouter(prefix="/notifications", tags=["通知渠道"])


def _notification_to_dict(n) -> dict:
    """将 NotificationChannel 对象转为字典"""
    return {
        "id": n.id,
        "name": n.name,
        "channel_type": n.channel_type,
        "webhook_url": n.webhook_url,
        "enabled": n.enabled,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("")
async def list_notifications(user=Depends(get_current_user)):
    """获取通知渠道列表"""
    items = await NotificationChannel.all().order_by("-created_at")
    return success(data=[_notification_to_dict(n) for n in items])


@router.post("")
async def create_notification(body: NotificationCreate, user=Depends(get_current_user)):
    """创建通知渠道"""
    n = await NotificationChannel.create(
        name=body.name,
        channel_type=body.channel_type,
        webhook_url=body.webhook_url,
        enabled=True,
    )
    return success(data=_notification_to_dict(n), message="创建成功")


@router.put("/{notification_id}")
async def update_notification(notification_id: int, body: NotificationUpdate, user=Depends(get_current_user)):
    """更新通知渠道"""
    n = await NotificationChannel.get_or_none(id=notification_id)
    if not n:
        return error(code=404, message="通知渠道不存在")

    update_fields = []
    if body.name is not None:
        n.name = body.name
        update_fields.append("name")
    if body.channel_type is not None:
        n.channel_type = body.channel_type
        update_fields.append("channel_type")
    if body.webhook_url is not None:
        n.webhook_url = body.webhook_url
        update_fields.append("webhook_url")
    if body.enabled is not None:
        n.enabled = body.enabled
        update_fields.append("enabled")

    n.updated_at = datetime.now()
    update_fields.append("updated_at")
    await n.save(update_fields=update_fields)

    return success(data=_notification_to_dict(n), message="更新成功")


@router.delete("/{notification_id}")
async def delete_notification(notification_id: int, user=Depends(get_current_user)):
    """删除通知渠道"""
    n = await NotificationChannel.get_or_none(id=notification_id)
    if not n:
        return error(code=404, message="通知渠道不存在")

    await n.delete()
    return success(message="已删除")
