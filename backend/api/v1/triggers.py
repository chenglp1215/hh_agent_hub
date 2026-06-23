import json as _json
import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
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

BEIJING_TZ = timezone(timedelta(hours=8))


async def _publish_wecom_refresh():
    """发布触发器刷新通知到 Redis"""
    try:
        from core.task_queue import get_task_queue
        tq = get_task_queue()
        await tq.connect()
        await tq._redis.publish("wecom_bot:refresh", "refresh")
    except Exception as e:
        logger.warning(f"Failed to publish wecom refresh: {e}")


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
        "wecom_chat_type": t.wecom_chat_type,
        "wecom_chat_id": t.wecom_chat_id,
        "wecom_user_id": t.wecom_user_id,
        "app_id": t.app_id,
        "app_name": t.app.name if hasattr(t, "app") and t.app else None,
        "message": t.message,
        "enabled": t.enabled,
        "notification_id": t.notification_id,
        "last_fired_at": t.last_fired_at.isoformat() if t.last_fired_at else None,
        "next_fire_at": t.next_fire_at.isoformat() if t.next_fire_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _execution_to_dict(e) -> dict:
    """将 TriggerExecution 对象转为字典"""
    return {
        "id": e.id,
        "trigger_id": e.trigger_id,
        "session_id": e.session_id,
        "task_id": e.task_id,
        "source": e.source,
        "status": e.status,
        "error_message": e.error_message,
        "duration_ms": e.duration_ms,
        "notified": e.notified,
        "started_at": e.started_at.isoformat() if e.started_at else None,
        "completed_at": e.completed_at.isoformat() if e.completed_at else None,
    }


@router.get("")
async def list_triggers(user=Depends(get_current_user)):
    """获取触发器列表"""
    triggers = await Trigger.all().select_related("app").order_by("-created_at")
    return success(data=[_trigger_to_dict(t) for t in triggers])


@router.post("/wecom-bot/generate-code")
async def generate_wecom_bind_code(body: dict, user=Depends(get_current_user)):
    """生成企微机器人绑定验证码"""
    app_id = body.get("app_id")
    if not app_id:
        return error(code=400, message="app_id 不能为空")

    app = await App.get_or_none(id=app_id)
    if not app:
        return error(code=400, message="应用不存在")

    # 生成 6 位随机验证码（大写字母+数字）
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    # 存入 Redis，TTL 300 秒
    tq = get_task_queue()
    await tq.connect()
    await tq._redis.set(
        f"wecom_bind:{code}",
        _json.dumps({"app_id": app_id, "user_id": user.id if user else None}),
        ex=300,
    )

    return success(data={
        "code": code,
        "expires_in": 300,
    })


@router.get("/wecom-bot/bind-status/{code}")
async def get_wecom_bind_status(code: str, user=Depends(get_current_user)):
    """查询验证码绑定状态"""
    tq = get_task_queue()
    await tq.connect()

    # 检查绑定结果
    result_data = await tq._redis.get(f"wecom_bind_result:{code}")
    if result_data:
        result = _json.loads(result_data)
        return success(data={
            "status": "bound",
            "chat_type": result.get("chat_type"),
            "chat_id": result.get("chat_id"),
        })

    # 检查验证码是否还存在（未过期）
    bind_data = await tq._redis.get(f"wecom_bind:{code}")
    if bind_data:
        return success(data={"status": "pending"})

    return error(code=404, message="验证码不存在或已过期")


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

    # 校验 wecom_bot 类型的参数完整
    if body.trigger_type == "wecom_bot":
        if not body.wecom_chat_type:
            return error(code=400, message="wecom_bot 类型必须指定 wecom_chat_type")
        if body.wecom_chat_type not in ("group", "user"):
            return error(code=400, message="wecom_chat_type 必须为 group 或 user")
        if body.wecom_chat_type == "group" and not body.wecom_chat_id:
            return error(code=400, message="group 类型必须指定 wecom_chat_id")
        if body.wecom_chat_type == "user" and not body.wecom_user_id:
            return error(code=400, message="user 类型必须指定 wecom_user_id")

    # 校验名称唯一性
    existing = await Trigger.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="触发器名称已存在")

    # 校验通知渠道
    if body.notification_id:
        from models.trigger import NotificationChannel
        nc = await NotificationChannel.get_or_none(id=body.notification_id)
        if not nc:
            return error(code=400, message="通知渠道不存在")

    t = await Trigger.create(
        name=body.name,
        description=body.description,
        trigger_type=body.trigger_type,
        interval_value=body.interval_value,
        interval_unit=body.interval_unit,
        cron_expression=body.cron_expression,
        wecom_chat_type=body.wecom_chat_type,
        wecom_chat_id=body.wecom_chat_id,
        wecom_user_id=body.wecom_user_id,
        app=app,
        message=body.message,
        enabled=True,
        notification_id=body.notification_id,
        created_by=user if user.id else None,
    )

    # 注册到调度器 (wecom_bot 类型不需要 APScheduler)
    if t.enabled and t.trigger_type != "wecom_bot":
        await add_job(t)
        # 重新获取 next_fire_at
        t.next_fire_at = await get_next_run_time(t.id)
        await t.save(update_fields=["next_fire_at"])

    await t.fetch_related("app")

    # wecom_bot 类型发布刷新通知
    if t.trigger_type == "wecom_bot":
        await _publish_wecom_refresh()

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
    if body.notification_id is not None:
        if body.notification_id:
            from models.trigger import NotificationChannel
            nc = await NotificationChannel.get_or_none(id=body.notification_id)
            if not nc:
                return error(code=400, message="通知渠道不存在")
        t.notification_id = body.notification_id
        update_fields.append("notification_id")
    if body.wecom_chat_type is not None:
        t.wecom_chat_type = body.wecom_chat_type
        update_fields.append("wecom_chat_type")
    if body.wecom_chat_id is not None:
        t.wecom_chat_id = body.wecom_chat_id
        update_fields.append("wecom_chat_id")
    if body.wecom_user_id is not None:
        t.wecom_user_id = body.wecom_user_id
        update_fields.append("wecom_user_id")

    t.updated_at = datetime.now()
    update_fields.append("updated_at")
    await t.save(update_fields=update_fields)

    # 同步调度器 (wecom_bot 类型不需要 APScheduler)
    if t.enabled and t.trigger_type != "wecom_bot":
        await reschedule_job(t)
        t.next_fire_at = await get_next_run_time(t.id)
        await t.save(update_fields=["next_fire_at"])
    elif t.trigger_type != "wecom_bot":
        await remove_job(t.id)
        t.next_fire_at = None
        await t.save(update_fields=["next_fire_at"])

    await t.fetch_related("app")

    # wecom_bot 类型发布刷新通知
    if t.trigger_type == "wecom_bot":
        await _publish_wecom_refresh()

    return success(data=_trigger_to_dict(t), message="更新成功")


@router.delete("/{trigger_id}")
async def delete_trigger(trigger_id: int, user=Depends(get_current_user)):
    """删除触发器"""
    t = await Trigger.get_or_none(id=trigger_id)
    if not t:
        return error(code=404, message="触发器不存在")

    # 从调度器移除
    await remove_job(t.id)

    trigger_type = t.trigger_type
    await t.delete()

    # wecom_bot 类型发布刷新通知
    if trigger_type == "wecom_bot":
        await _publish_wecom_refresh()

    return success(message="已删除")


@router.post("/{trigger_id}/execute")
async def execute_trigger(trigger_id: int, user=Depends(get_current_user)):
    """手动触发触发器立即执行一次"""
    t = await Trigger.get_or_none(id=trigger_id).select_related("app")
    if not t:
        return error(code=404, message="触发器不存在")
    if not t.enabled:
        return error(code=400, message="触发器已禁用，无法执行")
    if t.trigger_type == "wecom_bot":
        return error(code=400, message="企微机器人触发器不支持手动执行")

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

    # 写入执行记录
    from models.trigger import TriggerExecution
    execution = await TriggerExecution.create(
        trigger=t,
        session_id=session_id,
        task_id=task_id,
        source="manual",
        status="submitted",
    )

    # 更新 last_fired_at（不改变调度计划）
    t.last_fired_at = datetime.now(BEIJING_TZ).replace(tzinfo=None)
    await t.save(update_fields=["last_fired_at"])

    # 通知在 workflow_executor 任务完成后发送（不在这里发，避免任务未完成就通知）

    logger.info(f"Manual trigger {trigger_id} executed, task_id={task_id}")

    return success(data={
        "task_id": task_id,
        "session_id": session_id,
    }, message="已触发执行")


@router.get("/{trigger_id}/executions")
async def list_trigger_executions(
    trigger_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
):
    """获取触发器执行历史（分页）"""
    from models.trigger import TriggerExecution

    trigger = await Trigger.get_or_none(id=trigger_id)
    if not trigger:
        return error(code=404, message="触发器不存在")

    offset = (page - 1) * page_size
    total = await TriggerExecution.filter(trigger_id=trigger_id).count()
    items = await TriggerExecution.filter(trigger_id=trigger_id) \
        .order_by("-started_at") \
        .offset(offset) \
        .limit(page_size)

    return success(data={
        "total": total,
        "items": [_execution_to_dict(e) for e in items],
        "page": page,
        "page_size": page_size,
    })
