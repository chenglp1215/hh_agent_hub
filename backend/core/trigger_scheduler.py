"""APScheduler 调度器封装 — 触发器生命周期管理

职责：
  1. 应用启动时从数据库加载所有 enabled 触发器并注册 job
  2. 提供 add_job / remove_job / reschedule_job 供 API 层调用
  3. 触发器执行时通过 task_queue.enqueue() 提交任务

Job ID 约定: "trigger_{trigger_id}" (如 "trigger_1")
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.job import Job
from loguru import logger


# 全局调度器实例
_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> Optional[AsyncIOScheduler]:
    return _scheduler


async def init_scheduler():
    """初始化并启动调度器

    在 FastAPI lifespan 的 startup 阶段调用。
    从数据库加载所有 enabled=True 的触发器并注册 job。
    """
    global _scheduler
    if _scheduler is not None:
        logger.warning("Scheduler already initialized, skipping")
        return

    _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    _scheduler.start()
    logger.info("APScheduler started")

    # 从数据库加载所有启用触发器
    from models.trigger import Trigger
    triggers = await Trigger.filter(enabled=True).select_related("app")
    count = 0
    for trigger in triggers:
        try:
            await _register_job(trigger)
            count += 1
        except Exception as e:
            logger.error(f"Failed to register trigger {trigger.id} ({trigger.name}): {e}")
    logger.info(f"Loaded {count} enabled triggers into scheduler")


async def shutdown_scheduler():
    """关闭调度器

    在 FastAPI lifespan 的 shutdown 阶段调用。
    """
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("APScheduler shutdown")


def _build_apscheduler_trigger(trigger) -> any:
    """根据触发器配置构建 APScheduler trigger 对象"""
    if trigger.trigger_type == "interval":
        kw = {}
        if trigger.interval_unit == "minutes":
            kw["minutes"] = trigger.interval_value
        elif trigger.interval_unit == "hours":
            kw["hours"] = trigger.interval_value
        elif trigger.interval_unit == "days":
            kw["days"] = trigger.interval_value
        else:
            raise ValueError(f"Unknown interval_unit: {trigger.interval_unit}")
        return IntervalTrigger(**kw)
    elif trigger.trigger_type == "cron":
        parts = trigger.cron_expression.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {trigger.cron_expression}")
        return CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            timezone="Asia/Shanghai",
        )
    else:
        raise ValueError(f"Unknown trigger_type: {trigger.trigger_type}")


async def _trigger_execute(trigger_id: int):
    """触发器执行函数 — 由 APScheduler 调用

    1. 从数据库加载 trigger 和关联 app
    2. 校验 app 状态
    3. 创建临时 session
    4. 调用 task_queue.enqueue()
    5. 更新 last_fired_at 和 next_fire_at
    """
    from models.trigger import Trigger
    from models.session import Session
    from core.task_queue import get_task_queue

    trigger = await Trigger.get_or_none(id=trigger_id).select_related("app")
    if not trigger:
        logger.warning(f"Trigger {trigger_id} not found, skipping execution")
        return

    if not trigger.enabled:
        logger.warning(f"Trigger {trigger_id} is disabled, skipping execution")
        return

    app = trigger.app
    if not app or not app.enabled:
        logger.warning(f"App for trigger {trigger_id} is disabled, disabling trigger")
        trigger.enabled = False
        await trigger.save()
        await remove_job(trigger_id)
        return

    # 创建临时 session
    session_id = f"trigger_{trigger_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    session = await Session.create(
        id=session_id,
        app=app,
        user_id="",
        messages=[{"role": "user", "content": trigger.message}],
        expired_at=datetime.now() + timedelta(hours=1),
    )

    # 提交到队列
    task_queue = get_task_queue()
    task_id = await task_queue.enqueue(
        app_id=app.id,
        session_id=session_id,
        message=trigger.message,
        stream=False,
    )

    # 写入执行记录
    from models.trigger import TriggerExecution
    execution = await TriggerExecution.create(
        trigger=trigger,
        session_id=session_id,
        task_id=task_id,
        source="auto",
        status="submitted",
    )

    # 更新触发时间
    trigger.last_fired_at = datetime.now()
    trigger.next_fire_at = _get_job_next_run_time(trigger_id)
    await trigger.save()

    # 通知在 workflow_executor 任务完成后发送（不在这里发，避免任务未完成就通知）

    logger.info(f"Trigger {trigger_id} executed, task_id={task_id}, session_id={session_id}")


BEIJING_TZ = timezone(timedelta(hours=8))


def _get_job_next_run_time(trigger_id: int) -> Optional[datetime]:
    """获取 job 的下次运行时间（转换为北京时间 naive datetime）"""
    global _scheduler
    if not _scheduler:
        return None
    job = _scheduler.get_job(f"trigger_{trigger_id}")
    if job and job.next_run_time:
        # APScheduler 返回 UTC aware datetime，转为北京时间 naive datetime
        return job.next_run_time.astimezone(BEIJING_TZ).replace(tzinfo=None)
    return None


async def _register_job(trigger) -> Optional[Job]:
    """为触发器注册 APScheduler job"""
    global _scheduler
    if not _scheduler:
        return None

    job_id = f"trigger_{trigger.id}"
    aps_trigger = _build_apscheduler_trigger(trigger)

    # 如果同名 job 已存在，先移除
    existing = _scheduler.get_job(job_id)
    if existing:
        _scheduler.remove_job(job_id)

    job = _scheduler.add_job(
        _trigger_execute,
        trigger=aps_trigger,
        id=job_id,
        args=[trigger.id],
        replace_existing=True,
        misfire_grace_time=60,
    )

    # 更新 next_fire_at（转为北京时间 naive datetime）
    if job and job.next_run_time:
        trigger.next_fire_at = job.next_run_time.astimezone(BEIJING_TZ).replace(tzinfo=None)
        await trigger.save(update_fields=["next_fire_at"])

    logger.info(f"Registered job {job_id} for trigger '{trigger.name}'")
    return job


async def add_job(trigger) -> Optional[Job]:
    """添加触发器 job（创建或启用时调用）"""
    return await _register_job(trigger)


async def remove_job(trigger_id: int):
    """移除触发器 job（删除或禁用时调用）"""
    global _scheduler
    if not _scheduler:
        return
    job_id = f"trigger_{trigger_id}"
    existing = _scheduler.get_job(job_id)
    if existing:
        _scheduler.remove_job(job_id)
        logger.info(f"Removed job {job_id}")


async def reschedule_job(trigger) -> Optional[Job]:
    """重新调度触发器 job（更新时调用）"""
    return await _register_job(trigger)


async def get_next_run_time(trigger_id: int) -> Optional[datetime]:
    """获取指定触发器的下次运行时间（用于 API 响应）"""
    return _get_job_next_run_time(trigger_id)
