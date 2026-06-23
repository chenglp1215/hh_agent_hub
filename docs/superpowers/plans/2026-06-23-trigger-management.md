# Trigger Management Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a trigger management module that enables scheduled/periodic execution of published apps via APScheduler, reusing the existing task_queue.enqueue() workflow execution pipeline.

**Architecture:** Backend creates a `triggers` database table + APScheduler integration in FastAPI lifespan + 6 REST API endpoints. Frontend adds TriggerList and TriggerEditor pages following existing List+Editor pattern. Trigger execution reuses `task_queue.enqueue()` (same path as Chat API). APScheduler uses AsyncIOScheduler with MemoryJobStore; on startup all enabled triggers are loaded from DB into the scheduler; all CRUD operations synchronize scheduler state.

**Tech Stack:** FastAPI 0.115.6, Tortoise ORM, APScheduler 3.10+, Vue 3 + TypeScript + Ant Design Vue, Redis (via existing task_queue)

---

## File Structure

### Backend (new files)
| File | Responsibility |
|------|---------------|
| `backend/models/trigger.py` | Trigger ORM model (Tortoise) |
| `backend/schemas/trigger.py` | Pydantic request/response schemas |
| `backend/core/trigger_scheduler.py` | APScheduler wrapper: init, start, stop, add/remove/reschedule jobs |
| `backend/api/v1/triggers.py` | 6 API endpoints for trigger CRUD + manual execute |

### Backend (modified files)
| File | Change |
|------|--------|
| `backend/config.py` | Add `"models.trigger"` to MODELS list |
| `backend/api/v1/__init__.py` | Import and register triggers router |
| `backend/main.py` | Add scheduler init/shutdown in lifespan |
| `requirements.txt` | Add `apscheduler>=3.10,<4.0` |

### Frontend (new files)
| File | Responsibility |
|------|---------------|
| `frontend/src/api/triggers.ts` | Axios client for trigger API |
| `frontend/src/views/TriggerList.vue` | Trigger table list page |
| `frontend/src/views/TriggerEditor.vue` | Trigger create/edit form page |

### Frontend (modified files)
| File | Change |
|------|--------|
| `frontend/src/router/index.ts` | Add /triggers, /triggers/create, /triggers/:id/edit routes |
| `frontend/src/components/AppSidebar.vue` | Add "Trigger Management" menu item |

---

## Task B1: Add APScheduler dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add apscheduler to requirements.txt**

Append to requirements.txt:
```
# ============================================
# 调度引擎
# ============================================
apscheduler>=3.10,<4.0
```

Place it after the logging section (or in the existing dependency groups as a new group).

---

## Task B2: Create Trigger ORM model

**Files:**
- Create: `backend/models/trigger.py`
- Modify: `backend/config.py` (line ~55, append to MODELS list)

- [ ] **Step 1: Create the Trigger model file**

Create `backend/models/trigger.py`:

```python
from tortoise import fields, Model


class Trigger(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    description = fields.TextField(null=True)
    trigger_type = fields.CharField(max_length=20)  # "interval" | "cron"
    interval_value = fields.IntField(null=True)
    interval_unit = fields.CharField(max_length=10, null=True)  # "minutes" | "hours" | "days"
    cron_expression = fields.CharField(max_length=100, null=True)
    app = fields.ForeignKeyField("models.App", on_delete=fields.CASCADE)
    message = fields.TextField()
    enabled = fields.BooleanField(default=True)
    last_fired_at = fields.DatetimeField(null=True)
    next_fire_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "triggers"
```

- [ ] **Step 2: Register the model in config.py**

In `backend/config.py`, append `"models.trigger"` to the MODELS list (after `"models.chat_log"`):

```python
MODELS = [
    ...
    "models.chat_log",
    "models.workflow_trace",
    "models.trigger",  # <-- add this line
]
```

---

## Task B3: Create Trigger Pydantic schemas

**Files:**
- Create: `backend/schemas/trigger.py`

- [ ] **Step 1: Create the schema file**

Create `backend/schemas/trigger.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class TriggerTypeEnum(str, Enum):
    interval = "interval"
    cron = "cron"


class IntervalUnitEnum(str, Enum):
    minutes = "minutes"
    hours = "hours"
    days = "days"


class TriggerCreate(BaseModel):
    """创建触发器的请求体"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    trigger_type: TriggerTypeEnum
    interval_value: Optional[int] = Field(None, ge=1, le=99999)
    interval_unit: Optional[IntervalUnitEnum] = None
    cron_expression: Optional[str] = Field(None, max_length=100)
    app_id: int
    message: str = Field(..., min_length=1)

    class Config:
        use_enum_values = True


class TriggerUpdate(BaseModel):
    """更新触发器的请求体，所有字段可选"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    trigger_type: Optional[TriggerTypeEnum] = None
    interval_value: Optional[int] = Field(None, ge=1, le=99999)
    interval_unit: Optional[IntervalUnitEnum] = None
    cron_expression: Optional[str] = Field(None, max_length=100)
    app_id: Optional[int] = None
    message: Optional[str] = Field(None, min_length=1)
    enabled: Optional[bool] = None

    class Config:
        use_enum_values = True
```

---

## Task B4: Create APScheduler wrapper module

**Files:**
- Create: `backend/core/trigger_scheduler.py`

- [ ] **Step 1: Create the trigger_scheduler module**

Create `backend/core/trigger_scheduler.py`:

```python
"""APScheduler 调度器封装 — 触发器生命周期管理

职责：
  1. 应用启动时从数据库加载所有 enabled 触发器并注册 job
  2. 提供 add_job / remove_job / reschedule_job 供 API 层调用
  3. 触发器执行时通过 task_queue.enqueue() 提交任务

Job ID 约定: "trigger_{trigger_id}" (如 "trigger_1")
"""

from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.job import Job
from loguru import logger
from tortoise.expressions import Q

from config import settings


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
    5. 更新 last_fired_at
    """
    from models.trigger import Trigger
    from models.session import Session
    from core.task_queue import get_task_queue
    import uuid

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
        remove_job(trigger_id)
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

    # 更新触发时间
    trigger.last_fired_at = datetime.now()
    trigger.next_fire_at = _get_job_next_run_time(trigger_id)
    await trigger.save()

    logger.info(f"Trigger {trigger_id} executed, task_id={task_id}, session_id={session_id}")


def _get_job_next_run_time(trigger_id: int) -> Optional[datetime]:
    """获取 job 的下次运行时间"""
    global _scheduler
    if not _scheduler:
        return None
    job = _scheduler.get_job(f"trigger_{trigger_id}")
    if job and job.next_run_time:
        return job.next_run_time
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

    # 更新 next_fire_at
    if job and job.next_run_time:
        trigger.next_fire_at = job.next_run_time
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
```

---

## Task B5: Integrate scheduler into main.py lifespan

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Import and initialize scheduler in lifespan**

In `backend/main.py`, add the import and scheduler lifecycle:

At the top of the file, after existing imports:
```python
from core.trigger_scheduler import init_scheduler, shutdown_scheduler
```

In the `lifespan()` function, after `await seed_defaults()` and before `yield`:
```python
    await seed_defaults()
    # 初始化触发器调度器
    await init_scheduler()
    logger.info("Trigger scheduler ready")
    yield
    # 关闭调度器
    await shutdown_scheduler()
```

The full lifespan should look like:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Multi-Agent Platform...")
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas(safe=True)
    await seed_defaults()
    await init_scheduler()
    logger.info("Trigger scheduler ready")
    yield
    logger.info("Shutting down...")
    await shutdown_scheduler()
    await Tortoise.close_connections()
```

---

## Task B6: Create Trigger API routes

**Files:**
- Create: `backend/api/v1/triggers.py`
- Modify: `backend/api/v1/__init__.py`

- [ ] **Step 1: Create the triggers API module**

Create `backend/api/v1/triggers.py`:

```python
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
    """将 Trigger 对象转为字典（to_dict 的替代，包含 app_name）"""
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
```

- [ ] **Step 2: Register the router**

In `backend/api/v1/__init__.py`, add after the last import block (e.g., after chat_logs):

```python
from api.v1.triggers import router as triggers_router
router.include_router(triggers_router)
```

---

## Task F1: Create frontend API module

**Files:**
- Create: `frontend/src/api/triggers.ts`

- [ ] **Step 1: Create the triggers API module**

Create `frontend/src/api/triggers.ts`:

```typescript
import client from './client'

export const triggersApi = {
  list: () => client.get('/triggers'),
  get: (id: number) => client.get(`/triggers/${id}`),
  create: (data: any) => client.post('/triggers', data),
  update: (id: number, data: any) => client.put(`/triggers/${id}`, data),
  delete: (id: number) => client.delete(`/triggers/${id}`),
  execute: (id: number) => client.post(`/triggers/${id}/execute`),
}
```

**IMPORTANT**: axios response data properties use snake_case (e.g., `res.data.data.trigger_type`, not `res.data.data.triggerType`). The TypeScript interface uses camelCase for type checking only.

---

## Task F2: Create Trigger List page

**Files:**
- Create: `frontend/src/views/TriggerList.vue`

- [ ] **Step 1: Create the TriggerList component**

Create `frontend/src/views/TriggerList.vue`:

```vue
<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">触发器管理</h1>
      <a-button type="primary" @click="$router.push('/triggers/create')">
        <PlusOutlined /> 创建触发器
      </a-button>
    </div>

    <a-table :dataSource="triggers" :columns="columns" rowKey="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'trigger_type'">
          <a-tag :color="record.trigger_type === 'cron' ? 'blue' : 'green'">
            {{ record.trigger_type === 'cron' ? 'Cron' : '间隔' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'schedule'">
          <span v-if="record.trigger_type === 'interval'" class="text-sm">
            每 {{ record.interval_value }}
            {{ record.interval_unit === 'minutes' ? '分钟' : record.interval_unit === 'hours' ? '小时' : '天' }}
          </span>
          <code v-else class="text-xs px-1 py-0.5 rounded" style="background: #1a1a1c; color: #5e6ad2">
            {{ record.cron_expression }}
          </code>
        </template>
        <template v-if="column.key === 'enabled'">
          <a-switch
            :checked="record.enabled"
            @change="(checked: boolean) => handleToggleEnabled(record, checked)"
          />
        </template>
        <template v-if="column.key === 'app_name'">
          <span>{{ record.app_name || '-' }}</span>
        </template>
        <template v-if="column.key === 'actions'">
          <a-space>
            <a-button size="small" @click="$router.push(`/triggers/${record.id}/edit`)">编辑</a-button>
            <a-button size="small" type="primary" ghost @click="handleExecute(record.id)">立即执行</a-button>
            <a-popconfirm title="确定删除此触发器？" @confirm="handleDelete(record.id)">
              <a-button size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message, modal } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { triggersApi } from '@/api/triggers'

const triggers = ref<any[]>([])
const loading = ref(false)

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '类型', key: 'trigger_type', width: 80 },
  { title: '调度配置', key: 'schedule' },
  { title: '关联应用', key: 'app_name' },
  { title: '状态', key: 'enabled', width: 80 },
  { title: '上次触发', dataIndex: 'last_fired_at', key: 'last_fired_at' },
  { title: '下次触发', dataIndex: 'next_fire_at', key: 'next_fire_at' },
  { title: '操作', key: 'actions', width: 280 },
]

async function fetchList() {
  loading.value = true
  try {
    const res = await triggersApi.list()
    triggers.value = res.data.data || []
  } finally {
    loading.value = false
  }
}

async function handleToggleEnabled(record: any, checked: boolean) {
  try {
    await triggersApi.update(record.id, { enabled: checked })
    message.success(checked ? '已启用' : '已禁用')
    fetchList()
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  }
}

async function handleExecute(id: number) {
  try {
    const res = await triggersApi.execute(id)
    message.success('已触发执行')
  } catch (e: any) {
    message.error(e.response?.data?.message || '执行失败')
  }
}

async function handleDelete(id: number) {
  try {
    await triggersApi.delete(id)
    message.success('已删除')
    fetchList()
  } catch (e: any) {
    message.error(e.response?.data?.message || '删除失败')
  }
}

onMounted(fetchList)
</script>
```

---

## Task F3: Create Trigger Editor page

**Files:**
- Create: `frontend/src/views/TriggerEditor.vue`

- [ ] **Step 1: Create the TriggerEditor component**

Create `frontend/src/views/TriggerEditor.vue`:

```vue
<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">{{ isEdit ? '编辑' : '创建' }} 触发器</h1>
    <a-card class="max-w-2xl">
      <a-form :model="form" layout="vertical" @finish="handleSubmit">
        <a-form-item label="触发器名称" name="name" :rules="[{ required: true, message: '请输入触发器名称' }]">
          <a-input v-model:value="form.name" placeholder="如：每日巡检" />
        </a-form-item>

        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" placeholder="可选描述" />
        </a-form-item>

        <a-form-item label="触发类型" name="trigger_type" :rules="[{ required: true, message: '请选择触发类型' }]">
          <a-radio-group v-model:value="form.trigger_type">
            <a-radio value="interval">间隔触发</a-radio>
            <a-radio value="cron">Cron 表达式</a-radio>
          </a-radio-group>
        </a-form-item>

        <!-- Interval 配置 -->
        <template v-if="form.trigger_type === 'interval'">
          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item label="间隔数值" name="interval_value"
                :rules="[{ required: form.trigger_type === 'interval', message: '请输入间隔数值' }]">
                <a-input-number v-model:value="form.interval_value" :min="1" :max="99999" class="w-full" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="间隔单位" name="interval_unit"
                :rules="[{ required: form.trigger_type === 'interval', message: '请选择间隔单位' }]">
                <a-select v-model:value="form.interval_unit">
                  <a-select-option value="minutes">分钟</a-select-option>
                  <a-select-option value="hours">小时</a-select-option>
                  <a-select-option value="days">天</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>
        </template>

        <!-- Cron 配置 -->
        <template v-if="form.trigger_type === 'cron'">
          <a-form-item label="Cron 表达式" name="cron_expression"
            :rules="[{ required: form.trigger_type === 'cron', message: '请输入 cron 表达式' }]">
            <a-input v-model:value="form.cron_expression" placeholder="如：0 9 * * 1-5" />
          </a-form-item>
          <div class="mb-4">
            <span class="text-sm text-gray-400 mr-2">预设：</span>
            <a-button size="small" class="mr-1" @click="setCronPreset('0 * * * *')">每小时</a-button>
            <a-button size="small" class="mr-1" @click="setCronPreset('0 9 * * *')">每天 9:00</a-button>
            <a-button size="small" class="mr-1" @click="setCronPreset('0 9 * * 1-5')">工作日 9:00</a-button>
            <a-button size="small" @click="setCronPreset('0 0 1 * *')">每月1日</a-button>
          </div>
        </template>

        <a-form-item label="关联应用" name="app_id"
          :rules="[{ required: true, message: '请选择关联应用' }]">
          <a-select
            v-model:value="form.app_id"
            show-search
            option-filter-prop="label"
            placeholder="选择已启用的应用"
          >
            <a-select-option
              v-for="app in enabledApps"
              :key="app.id"
              :value="app.id"
              :label="app.name"
            >
              {{ app.name }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="触发消息内容" name="message"
          :rules="[{ required: true, message: '请输入触发消息内容' }]">
          <a-textarea v-model:value="form.message" :rows="3" placeholder="输入触发时发送的 Chat 消息内容" />
        </a-form-item>

        <a-form-item>
          <a-space>
            <a-button type="primary" html-type="submit" :loading="submitting">保存</a-button>
            <a-button @click="$router.back()">取消</a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { triggersApi } from '@/api/triggers'
import { appsApi } from '@/api/apps'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const submitting = ref(false)
const enabledApps = ref<any[]>([])

const form = ref({
  name: '',
  description: '',
  trigger_type: 'interval' as 'interval' | 'cron',
  interval_value: undefined as number | undefined,
  interval_unit: undefined as string | undefined,
  cron_expression: '',
  app_id: undefined as number | undefined,
  message: '',
})

const presetCronLabels: Record<string, string> = {
  '0 * * * *': '每小时',
  '0 9 * * *': '每天 9:00',
  '0 9 * * 1-5': '工作日 9:00',
  '0 0 1 * *': '每月1日',
}

function setCronPreset(expr: string) {
  form.value.cron_expression = expr
}

onMounted(async () => {
  // 加载已启用的应用列表
  const res = await appsApi.list()
  enabledApps.value = (res.data.data || []).filter((a: any) => a.enabled)

  if (isEdit.value) {
    const res = await triggersApi.get(Number(route.params.id))
    const d = res.data.data
    form.value = {
      name: d.name,
      description: d.description || '',
      trigger_type: d.trigger_type,
      interval_value: d.interval_value,
      interval_unit: d.interval_unit,
      cron_expression: d.cron_expression || '',
      app_id: d.app_id,
      message: d.message,
    }
  }
})

async function handleSubmit() {
  submitting.value = true
  try {
    const payload: Record<string, any> = { ...form.value }
    // 清理 interval/cron 互斥字段
    if (payload.trigger_type === 'interval') {
      payload.cron_expression = null
    } else {
      payload.interval_value = null
      payload.interval_unit = null
    }

    if (isEdit.value) {
      await triggersApi.update(Number(route.params.id), payload)
    } else {
      await triggersApi.create(payload)
    }
    message.success('保存成功')
    router.push('/triggers')
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}
</script>
```

---

## Task F4: Register frontend routes and sidebar

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/AppSidebar.vue`

- [ ] **Step 1: Add trigger routes**

In `frontend/src/router/index.ts`, add after the apps routes (around line 25):

```typescript
        // Trigger management
        { path: 'triggers', name: 'TriggerList', component: () => import('@/views/TriggerList.vue'), meta: { title: '触发器管理' } },
        { path: 'triggers/create', name: 'TriggerCreate', component: () => import('@/views/TriggerEditor.vue'), meta: { title: '创建触发器' } },
        { path: 'triggers/:id/edit', name: 'TriggerEdit', component: () => import('@/views/TriggerEditor.vue'), meta: { title: '编辑触发器' }, props: true },
```

- [ ] **Step 2: Add sidebar menu item**

In `frontend/src/components/AppSidebar.vue`, add a new sub-menu for triggers. Insert after the apps sub-menu (around line 60):

```html
      <a-sub-menu key="triggers" class="menu-sub">
        <template #icon>
          <span class="menu-icon"><FieldTimeOutlined /></span>
        </template>
        <template #title>触发器管理</template>
        <a-menu-item key="/triggers">触发器列表</a-menu-item>
      </a-sub-menu>
```

Also add the icon import at the top of the script section:
```typescript
import {
  DashboardOutlined, RobotOutlined, ApartmentOutlined,
  AppstoreOutlined, DatabaseOutlined, LineChartOutlined, SettingOutlined,
  MenuFoldOutlined, MenuUnfoldOutlined, FieldTimeOutlined,
} from '@ant-design/icons-vue'
```

Note: Add `FieldTimeOutlined` to the existing icon import list. Also add `triggers` to the `openKeys` initial value array so the submenu can expand:

```typescript
const openKeys = ref<string[]>(['agents', 'workflows', 'apps', 'triggers', 'resources', 'monitor', 'settings'])
```

---

## Task A1: API endpoint tests

**Files:**
- Create: `backend/tests/test_triggers_api.py`

- [ ] **Step 1: Create comprehensive API tests**

Create `backend/tests/test_triggers_api.py`:

```python
"""触发器管理 API 测试

测试范围:
  - CRUD 全部 5 个端点
  - 手动执行端点
  - 参数校验（interval/cron 互斥字段、app 状态校验、名称唯一性）
  - enabled/disabled 状态变更

注意：
  1. 测试依赖数据库（SQLite 或 MySQL），需要 Tortoise ORM 初始化
  2. 测试前需先创建测试 App 记录
  3. APScheduler 可 mock 掉，不依赖真实调度
"""

import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from models.app import App
from models.trigger import Trigger
from models.user import User
from utils.jwt import create_access_token


@pytest.fixture(autouse=True)
async def setup_db():
    """初始化数据库（SQLite 内存模式）和测试数据"""
    from tortoise import Tortoise
    from config import TORTOISE_ORM, settings

    # 使用 SQLite 内存数据库
    test_config = {
        "connections": {"default": "sqlite://:memory:"},
        "apps": {
            "models": {
                "models": TORTOISE_ORM["apps"]["models"]["models"],
                "default_connection": "default",
            }
        },
        "timezone": "Asia/Shanghai",
    }
    await Tortoise.init(config=test_config)
    await Tortoise.generate_schemas(safe=True)

    # 创建测试用户
    user = await User.create(username="testadmin", role="admin", password_hash="x")

    # 创建测试应用
    app_a = await App.create(name="test-app-a", api_key="test-key-a", enabled=True, created_by=user)
    app_b = await App.create(name="test-app-b", api_key="test-key-b", enabled=True, created_by=user)
    app_disabled = await App.create(name="test-app-disabled", api_key="test-key-disabled", enabled=False, created_by=user)

    yield {
        "user": user,
        "app_a": app_a,
        "app_b": app_b,
        "app_disabled": app_disabled,
    }

    await Tortoise.close_connections()


@pytest.fixture
async def token(setup_db):
    """生成测试 JWT token"""
    user = setup_db["user"]
    return create_access_token(data={"sub": str(user.id)})


@pytest.fixture
async def client(token):
    """创建测试 HTTP 客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


@pytest.mark.asyncio
async def test_create_interval_trigger(client, setup_db):
    """创建 interval 类型触发器"""
    app_a = setup_db["app_a"]
    resp = await client.post("/api/v1/triggers", json={
        "name": "test-interval",
        "trigger_type": "interval",
        "interval_value": 30,
        "interval_unit": "minutes",
        "app_id": app_a.id,
        "message": "执行巡检任务",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["name"] == "test-interval"
    assert data["data"]["trigger_type"] == "interval"
    assert data["data"]["interval_value"] == 30
    assert data["data"]["interval_unit"] == "minutes"
    assert data["data"]["enabled"] is True


@pytest.mark.asyncio
async def test_create_cron_trigger(client, setup_db):
    """创建 cron 类型触发器"""
    app_a = setup_db["app_a"]
    resp = await client.post("/api/v1/triggers", json={
        "name": "test-cron",
        "trigger_type": "cron",
        "cron_expression": "0 9 * * 1-5",
        "app_id": app_a.id,
        "message": "早上好",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["trigger_type"] == "cron"
    assert data["data"]["cron_expression"] == "0 9 * * 1-5"


@pytest.mark.asyncio
async def test_create_trigger_with_disabled_app(client, setup_db):
    """创建触发器关联已禁用的应用应报错"""
    app_disabled = setup_db["app_disabled"]
    resp = await client.post("/api/v1/triggers", json={
        "name": "test-disabled-app",
        "trigger_type": "interval",
        "interval_value": 10,
        "interval_unit": "minutes",
        "app_id": app_disabled.id,
        "message": "test",
    })
    assert resp.status_code == 400
    data = resp.json()
    assert data["code"] != 0


@pytest.mark.asyncio
async def test_create_trigger_duplicate_name(client, setup_db):
    """重复名称应报错"""
    app_a = setup_db["app_a"]
    # 创建第一个
    await client.post("/api/v1/triggers", json={
        "name": "duplicate-name",
        "trigger_type": "interval",
        "interval_value": 10,
        "interval_unit": "minutes",
        "app_id": app_a.id,
        "message": "test",
    })
    # 创建同名的第二个
    resp = await client.post("/api/v1/triggers", json={
        "name": "duplicate-name",
        "trigger_type": "interval",
        "interval_value": 20,
        "interval_unit": "minutes",
        "app_id": app_a.id,
        "message": "test2",
    })
    assert resp.status_code == 400
    data = resp.json()
    assert data["code"] != 0


@pytest.mark.asyncio
async def test_list_triggers(client, setup_db):
    """列表查询"""
    app_a = setup_db["app_a"]
    await client.post("/api/v1/triggers", json={
        "name": "list-test-1",
        "trigger_type": "interval",
        "interval_value": 30,
        "interval_unit": "minutes",
        "app_id": app_a.id,
        "message": "msg1",
    })
    await client.post("/api/v1/triggers", json={
        "name": "list-test-2",
        "trigger_type": "cron",
        "cron_expression": "0 9 * * *",
        "app_id": app_a.id,
        "message": "msg2",
    })

    resp = await client.get("/api/v1/triggers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert len(data["data"]) == 2


@pytest.mark.asyncio
async def test_get_trigger_detail(client, setup_db):
    """获取触发器详情"""
    app_a = setup_db["app_a"]
    create_resp = await client.post("/api/v1/triggers", json={
        "name": "detail-test",
        "trigger_type": "interval",
        "interval_value": 15,
        "interval_unit": "minutes",
        "app_id": app_a.id,
        "message": "detail msg",
    })
    trigger_id = create_resp.json()["data"]["id"]

    resp = await client.get(f"/api/v1/triggers/{trigger_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["name"] == "detail-test"
    assert data["data"]["app_name"] is not None


@pytest.mark.asyncio
async def test_update_trigger(client, setup_db):
    """更新触发器"""
    app_a = setup_db["app_a"]
    create_resp = await client.post("/api/v1/triggers", json={
        "name": "update-test",
        "trigger_type": "interval",
        "interval_value": 10,
        "interval_unit": "minutes",
        "app_id": app_a.id,
        "message": "original",
    })
    trigger_id = create_resp.json()["data"]["id"]

    resp = await client.put(f"/api/v1/triggers/{trigger_id}", json={
        "name": "updated-name",
        "message": "updated message",
        "enabled": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["name"] == "updated-name"
    assert data["data"]["message"] == "updated message"
    assert data["data"]["enabled"] is False


@pytest.mark.asyncio
async def test_delete_trigger(client, setup_db):
    """删除触发器"""
    app_a = setup_db["app_a"]
    create_resp = await client.post("/api/v1/triggers", json={
        "name": "delete-test",
        "trigger_type": "interval",
        "interval_value": 5,
        "interval_unit": "minutes",
        "app_id": app_a.id,
        "message": "to be deleted",
    })
    trigger_id = create_resp.json()["data"]["id"]

    resp = await client.delete(f"/api/v1/triggers/{trigger_id}")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    # 确认已删除
    get_resp = await client.get(f"/api/v1/triggers/{trigger_id}")
    assert get_resp.json()["code"] == 404


@pytest.mark.asyncio
async def test_execute_trigger(client, setup_db):
    """手动触发执行"""
    app_a = setup_db["app_a"]
    create_resp = await client.post("/api/v1/triggers", json={
        "name": "execute-test",
        "trigger_type": "interval",
        "interval_value": 60,
        "interval_unit": "minutes",
        "app_id": app_a.id,
        "message": "execute me",
    })
    trigger_id = create_resp.json()["data"]["id"]

    resp = await client.post(f"/api/v1/triggers/{trigger_id}/execute")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "task_id" in data["data"]
    assert "session_id" in data["data"]


@pytest.mark.asyncio
async def test_execute_disabled_trigger(client, setup_db):
    """手动执行已禁用的触发器应报错"""
    app_a = setup_db["app_a"]
    create_resp = await client.post("/api/v1/triggers", json={
        "name": "disabled-execute",
        "trigger_type": "interval",
        "interval_value": 10,
        "interval_unit": "minutes",
        "app_id": app_a.id,
        "message": "test",
    })
    trigger_id = create_resp.json()["data"]["id"]

    # 禁用
    await client.put(f"/api/v1/triggers/{trigger_id}", json={"enabled": False})

    # 尝试执行
    resp = await client.post(f"/api/v1/triggers/{trigger_id}/execute")
    assert resp.status_code == 400
    data = resp.json()
    assert data["code"] != 0


@pytest.mark.asyncio
async def test_get_nonexistent_trigger_returns_404(client, setup_db):
    """获取不存在的触发器返回 404"""
    resp = await client.get("/api/v1/triggers/99999")
    assert resp.status_code == 200  # API 返回 200 但 code!=0
    data = resp.json()
    assert data["code"] == 404
```

---

## Self-Review Checklist

### Spec Coverage

| Spec Requirement | Covered By |
|---|---|
| 创建触发器 (interval) | Task B6 (POST create), Task A1 (test_create_interval_trigger) |
| 创建触发器 (cron) | Task B6, Task A1 (test_create_cron_trigger) |
| 关联不存在/已禁用应用时错误 | Task B6 (400 validation), Task A1 (test_create_trigger_with_disabled_app) |
| 查询触发器列表 | Task B6 (GET list), Task A1 (test_list_triggers) |
| 查询触发器详情 | Task B6 (GET detail), Task A1 (test_get_trigger_detail) |
| 更新触发器 | Task B6 (PUT), Task A1 (test_update_trigger) |
| 删除触发器 | Task B6 (DELETE), Task A1 (test_delete_trigger) |
| 手动触发执行 | Task B6 (POST execute), Task A1 (test_execute_trigger) |
| 执行已禁用触发器报错 | Task B6 (400 in execute), Task A1 (test_execute_disabled_trigger) |
| 名称唯一性 | Task B6 (POST/PUT duplicate check), Task A1 (test_create_trigger_duplicate_name) |
| 间隔值有效约束 | Task B6 (schema validation: ge=1, le=99999) |
| 不合法 cron 表达式校验 | Task B6 (5-field check in POST) |
| 调度器启动时加载 enabled | Task B4 (init_scheduler loads enabled=True) |
| 调度器状态同步（创建/更新/删除/启用/禁用） | Task B4 (add_job/remove_job/reschedule_job) + Task B6 (calls these in each handler) |
| 下次触发时间计算 | Task B4 (_register_job updates next_fire_at) |
| 前端 TriggerList 页面 | Task F2 |
| 前端 TriggerEditor 页面 | Task F3 |
| 前端路由 | Task F4 (router/index.ts) |
| 侧边栏菜单 | Task F4 (AppSidebar.vue) |

### Placeholder Scan

No placeholders found. All steps contain complete code, exact file paths, and actionable content.

### Type Consistency

- Trigger model fields match schema fields (trigger_type, interval_value, interval_unit, cron_expression, app_id, message, enabled, last_fired_at, next_fire_at)
- _trigger_to_dict() field names match the API contract file
- Frontend API module methods (list, get, create, update, delete, execute) match backend routes
- Frontend form fields match request body fields (all snake_case for runtime compatibility)
