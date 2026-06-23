import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from models.trigger import Trigger
from models.app import App
from schemas.trigger import TriggerCreate, TriggerUpdate
from api.deps import get_current_user
from utils.response import success, error
from core.trigger_scheduler import add_job, remove_job, reschedule_job, get_next_run_time
from core.task_queue import get_task_queue
from models.session import Session
from loguru import logger

router = APIRouter(prefix="/triggers", tags=["触发器"])


def _trigger_to_dict(t) -> dict:
    """将 Trigger 对象转为字典，包含 app_name 联表字段"""
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "trigger_type": t.trigger_type,
        "interval_value": t.interval_value,
        "interval_unit": t.interval_unit,
        "cron_expression": t.cron_expression,
        "app_id": t.app_id,
        "app_name": t.app.name if hasattr(t, "app") and t.app else None,
        "message": t.message,
        "enabled": t.enabled,
        "last_fired_at": t.last_fired_at.isoformat() if t.last_fired_at else None,
        "next_fire_at": t.next_fire_at.isoformat() if t.next_fire_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.get("")
async def list_triggers(user=Depends(get_current_user)):
    """获取触发器列表"""
    triggers = await Trigger.all().select_related("app").order_by("-created_at")
    return success(data=[_trigger_to_dict(t) for t in triggers])


@router.get("/{trigger_id}")
async def get_trigger(trigger_id: int, user=Depends(get_current_user)):
    """获取触发器详情"""
    t = await Trigger.get_or_none(id=trigger_id).select_related("app")
    if not t:
        return error(code=404, message="触发器不存在")
    return success(data=_trigger_to_dict(t))


@router.post("")
async def create_trigger(body: TriggerCreate, user=Depends(get_current_user)):
    """创建触发器"""
    # 校验关联应用
    app = await App.get_or_none(id=body.app_id)
    if not app:
        return error(code=400, message="应用不存在")
    if not app.enabled:
        return error(code=400, message="只能关联已启用的应用")

    # 校验 interval 类型的参数完整
    if body.trigger_type == "interval":
        if body.interval_value is None or body.interval_unit is None:
            return error(code=400, message="interval 类型必须指定 interval_value 和 interval_unit")

    # 校验 cron 类型的参数完整
    if body.trigger_type == "cron":
        if not body.cron_expression:
            return error(code=400, message="cron 类型必须指定 cron_expression")
        # 简单校验 cron 表达式格式
        parts = body.cron_expression.strip().split()
        if len(parts) != 5:
            return error(code=400, message="cron 表达式格式不正确，需要 5 个字段")

    # 校验名称唯一性
    existing = await Trigger.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="触发器名称已存在")

    t = await Trigger.create(
        name=body.name,
        description=body.description,
        trigger_type=body.trigger_type,
        interval_value=body.interval_value,
        interval_unit=body.interval_unit,
        cron_expression=body.cron_expression,
        app=app,
        message=body.message,
        enabled=True,
        created_by=user if user.id else None,
    )

    # 注册到调度器
    if t.enabled:
        await add_job(t)
        # 重新获取 next_fire_at
        t.next_fire_at = await get_next_run_time(t.id)
        await t.save(update_fields=["next_fire_at"])

    await t.fetch_related("app")
    return success(data=_trigger_to_dict(t), message="创建成功")


@router.put("/{trigger_id}")
async def update_trigger(trigger_id: int, body: TriggerUpdate, user=Depends(get_current_user)):
    """更新触发器"""
    t = await Trigger.get_or_none(id=trigger_id)
    if not t:
        return error(code=404, message="触发器不存在")

    # 校验关联应用
    if body.app_id is not None:
        app = await App.get_or_none(id=body.app_id)
        if not app:
            return error(code=400, message="应用不存在")
        if not app.enabled:
            return error(code=400, message="只能关联已启用的应用")
        t.app = app

    # 更新字段
    update_fields = []
    if body.name is not None:
        # 校验名称唯一性
        existing = await Trigger.get_or_none(name=body.name)
        if existing and existing.id != trigger_id:
            return error(code=400, message="触发器名称已存在")
        t.name = body.name
        update_fields.append("name")
    if body.description is not None:
        t.description = body.description
        update_fields.append("description")
    if body.trigger_type is not None:
        t.trigger_type = body.trigger_type
        update_fields.append("trigger_type")
    if body.interval_value is not None:
        t.interval_value = body.interval_value
        update_fields.append("interval_value")
    if body.interval_unit is not None:
        t.interval_unit = body.interval_unit
        update_fields.append("interval_unit")
    if body.cron_expression is not None:
        t.cron_expression = body.cron_expression
        update_fields.append("cron_expression")
    if body.app_id is not None:
        update_fields.append("app_id")
    if body.message is not None:
        t.message = body.message
        update_fields.append("message")
    if body.enabled is not None:
        t.enabled = body.enabled
        update_fields.append("enabled")

    t.updated_at = datetime.now()
    update_fields.append("updated_at")
    await t.save(update_fields=update_fields)

    # 同步调度器
    if t.enabled:
        await reschedule_job(t)
        t.next_fire_at = await get_next_run_time(t.id)
        await t.save(update_fields=["next_fire_at"])
    else:
        await remove_job(t.id)
        t.next_fire_at = None
        await t.save(update_fields=["next_fire_at"])

    await t.fetch_related("app")
    return success(data=_trigger_to_dict(t), message="更新成功")


@router.delete("/{trigger_id}")
async def delete_trigger(trigger_id: int, user=Depends(get_current_user)):
    """删除触发器"""
    t = await Trigger.get_or_none(id=trigger_id)
    if not t:
        return error(code=404, message="触发器不存在")

    # 从调度器移除
    await remove_job(t.id)

    await t.delete()
    return success(message="已删除")


@router.post("/{trigger_id}/execute")
async def execute_trigger(trigger_id: int, user=Depends(get_current_user)):
    """手动触发触发器立即执行一次"""
    t = await Trigger.get_or_none(id=trigger_id).select_related("app")
    if not t:
        return error(code=404, message="触发器不存在")
    if not t.enabled:
        return error(code=400, message="触发器已禁用，无法执行")

    app = t.app
    if not app or not app.enabled:
        return error(code=400, message="关联应用不存在或已禁用")

    # 创建临时 session
    session_id = f"trigger_manual_{trigger_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    session = await Session.create(
        id=session_id,
        app=app,
        user_id="",
        messages=[{"role": "user", "content": t.message}],
        expired_at=datetime.now() + timedelta(hours=1),
    )

    # 提交到队列
    task_queue = get_task_queue()
    task_id = await task_queue.enqueue(
        app_id=app.id,
        session_id=session_id,
        message=t.message,
        stream=False,
    )

    # 更新 last_fired_at（不改变调度计划）
    t.last_fired_at = datetime.now()
    await t.save(update_fields=["last_fired_at"])

    logger.info(f"Manual trigger {trigger_id} executed, task_id={task_id}")

    return success(data={
        "task_id": task_id,
        "session_id": session_id,
    }, message="已触发执行")
