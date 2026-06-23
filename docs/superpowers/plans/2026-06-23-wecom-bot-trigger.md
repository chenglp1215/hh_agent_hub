# Wecom Bot Trigger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "Wecom Bot" trigger type that routes enterprise WeChat messages to workflow executions via WebSocket long connection.

**Architecture:** A new `wecom-bot` Docker container maintains a persistent WebSocket connection to WeCom's open API using the aibot SDK. It loads trigger mappings into memory at startup, refreshes via Redis pub/sub, and routes incoming messages to matching triggers. The main API container exposes new endpoints for the handshake binding flow (generate code, poll status). The existing `task_queue.enqueue()` and `TriggerExecution` patterns are reused for workflow execution.

**Tech Stack:** Python 3.11, FastAPI, Tortoise ORM, Redis (pub/sub + string), aibot SDK (websockets + pyee), Vue 3 + Ant Design Vue

**API Contract:** `outputs/contracts/task-wecom-bot-api-contract.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `backend/core/wecom_bot/__init__.py` | Package init |
| `backend/core/wecom_bot/aibot_sdk/__init__.py` | aibot SDK package init |
| `backend/core/wecom_bot/aibot_sdk/ws.py` | WebSocket connection manager (copied from reference) |
| `backend/core/wecom_bot/aibot_sdk/client.py` | WSClient high-level interface (copied) |
| `backend/core/wecom_bot/aibot_sdk/message_handler.py` | Message dispatcher (copied) |
| `backend/core/wecom_bot/aibot_sdk/types.py` | Type definitions (copied) |
| `backend/core/wecom_bot/aibot_sdk/utils.py` | Utility functions (copied) |
| `backend/core/wecom_bot/aibot_sdk/crypto_utils.py` | Crypto utilities (copied) |
| `backend/core/wecom_bot/aibot_sdk/logger.py` | Default logger (copied) |
| `backend/core/wecom_bot/aibot_sdk/api.py` | API client (copied) |
| `backend/core/wecom_bot/message_bridge.py` | Message routing + workflow execution + streaming reply |
| `backend/core/wecom_bot/connector.py` | WSClient lifecycle management + credential loading |
| `backend/core/wecom_bot/__main__.py` | Standalone process entry point |
| `Dockerfile.wecom-bot` | Docker image for wecom-bot container |
| `frontend/src/components/WecomBotBindSteps.vue` | Multi-step binding wizard component |

### Modified Files

| File | Changes |
|------|---------|
| `backend/models/trigger.py` | Add `wecom_chat_type`, `wecom_chat_id`, `wecom_user_id` fields to Trigger model |
| `backend/schemas/trigger.py` | Add `wecom_bot` to TriggerTypeEnum, add WecomChatTypeEnum, extend TriggerCreate/TriggerUpdate |
| `backend/api/v1/triggers.py` | Update `_trigger_to_dict()`, update `create_trigger()` validation, add `generate-code` and `bind-status` endpoints, publish Redis refresh on create/update/delete |
| `backend/core/trigger_scheduler.py` | Skip APScheduler registration for wecom_bot type triggers |
| `docker-compose.yml` | Add `wecom-bot` service |
| `requirements.txt` | Add `websockets>=12.0`, `pyee>=11.0`, `certifi` |
| `frontend/src/api/triggers.ts` | Add `generateCode()` and `getBindStatus()` API methods |
| `frontend/src/views/TriggerEditor.vue` | Add "wecom_bot" radio option + multi-step binding flow |
| `frontend/src/views/TriggerList.vue` | Add wecom_bot type badge display |

---

## Backend Tasks

### Task B1: Copy aibot SDK and add dependencies

**Files:**
- Create: `backend/core/wecom_bot/__init__.py`
- Create: `backend/core/wecom_bot/aibot_sdk/__init__.py`
- Create: `backend/core/wecom_bot/aibot_sdk/ws.py`
- Create: `backend/core/wecom_bot/aibot_sdk/client.py`
- Create: `backend/core/wecom_bot/aibot_sdk/message_handler.py`
- Create: `backend/core/wecom_bot/aibot_sdk/types.py`
- Create: `backend/core/wecom_bot/aibot_sdk/utils.py`
- Create: `backend/core/wecom_bot/aibot_sdk/crypto_utils.py`
- Create: `backend/core/wecom_bot/aibot_sdk/logger.py`
- Create: `backend/core/wecom_bot/aibot_sdk/api.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p backend/core/wecom_bot/aibot_sdk
touch backend/core/wecom_bot/__init__.py
touch backend/core/wecom_bot/aibot_sdk/__init__.py
```

- [ ] **Step 2: Copy aibot SDK files from reference project**

Copy all 8 files from `E:\wechat-bot-dev\AIBUILD\qw_bot_claude\venv\Lib\site-packages\aibot\` to `backend/core/wecom_bot/aibot_sdk/`:
- `ws.py`
- `client.py`
- `message_handler.py`
- `types.py`
- `utils.py`
- `crypto_utils.py`
- `logger.py`
- `api.py`

```bash
cp E:/wechat-bot-dev/AIBUILD/qw_bot_claude/venv/Lib/site-packages/aibot/*.py backend/core/wecom_bot/aibot_sdk/
```

- [ ] **Step 3: Update relative imports in aibot SDK files**

In each copied file, update imports from `.types`, `.utils`, `.ws`, `.client`, `.message_handler`, `.api`, `.crypto_utils`, `.logger` to use the new package path. The relative imports (`.types`, `.utils`, etc.) should work as-is since they are within the same package.

Verify `client.py` imports:
```python
from .api import WeComApiClient
from .crypto_utils import decrypt_file
from .logger import DefaultLogger
from .message_handler import MessageHandler
from .types import WsCmd, WsFrame, WsFrameHeaders, WSClientOptions
from .utils import generate_req_id
from .ws import WsConnectionManager
```

- [ ] **Step 4: Add Python dependencies to requirements.txt**

Append to `requirements.txt`:
```
# WebSocket (aibot SDK for WeCom bot)
websockets>=12.0
pyee>=11.0
certifi
```

- [ ] **Step 5: Verify SDK imports**

```bash
cd E:/wechat-bot-dev/AIBUILD/hh_agent_hub
PYTHONPATH=backend python -c "from core.wecom_bot.aibot_sdk.client import WSClient; from core.wecom_bot.aibot_sdk.types import WSClientOptions; print('aibot SDK import OK')"
```

Expected: `aibot SDK import OK`

- [ ] **Step 6: Commit**

```bash
git add backend/core/wecom_bot/ requirements.txt
git commit -m "feat(wecom-bot): integrate aibot SDK and add dependencies"
```

---

### Task B2: Extend Trigger model with wecom_bot fields

**Files:**
- Modify: `backend/models/trigger.py`
- Modify: `backend/schemas/trigger.py`

- [ ] **Step 1: Add fields to Trigger model**

In `backend/models/trigger.py`, add three new nullable fields to the `Trigger` class after `cron_expression`:

```python
class Trigger(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    description = fields.TextField(null=True)
    trigger_type = fields.CharField(max_length=20)  # "interval" | "cron" | "wecom_bot"
    interval_value = fields.IntField(null=True)
    interval_unit = fields.CharField(max_length=10, null=True)  # "minutes" | "hours" | "days"
    cron_expression = fields.CharField(max_length=100, null=True)
    # --- NEW: wecom_bot fields ---
    wecom_chat_type = fields.CharField(max_length=10, null=True)  # "group" | "user"
    wecom_chat_id = fields.CharField(max_length=100, null=True)
    wecom_user_id = fields.CharField(max_length=100, null=True)
    # --- END NEW ---
    app = fields.ForeignKeyField("models.App", on_delete=fields.CASCADE)
    message = fields.TextField()
    enabled = fields.BooleanField(default=True)
    notification = fields.ForeignKeyField("models.NotificationChannel", null=True, on_delete=fields.SET_NULL)
    last_fired_at = fields.DatetimeField(null=True)
    next_fire_at = fields.DatetimeField(null=True)
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "triggers"
```

- [ ] **Step 2: Update schemas**

In `backend/schemas/trigger.py`, add the new enum and fields:

```python
class TriggerTypeEnum(str, Enum):
    interval = "interval"
    cron = "cron"
    wecom_bot = "wecom_bot"  # NEW


class WecomChatTypeEnum(str, Enum):  # NEW
    group = "group"
    user = "user"


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
    notification_id: Optional[int] = None
    # NEW: wecom_bot fields
    wecom_chat_type: Optional[WecomChatTypeEnum] = None
    wecom_chat_id: Optional[str] = Field(None, max_length=100)
    wecom_user_id: Optional[str] = Field(None, max_length=100)

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
    notification_id: Optional[int] = None
    # NEW: wecom_bot fields
    wecom_chat_type: Optional[WecomChatTypeEnum] = None
    wecom_chat_id: Optional[str] = Field(None, max_length=100)
    wecom_user_id: Optional[str] = Field(None, max_length=100)

    class Config:
        use_enum_values = True
```

- [ ] **Step 3: Commit**

```bash
git add backend/models/trigger.py backend/schemas/trigger.py
git commit -m "feat(wecom-bot): extend Trigger model and schemas with wecom_bot fields"
```

---

### Task B3: Update trigger API endpoints

**Files:**
- Modify: `backend/api/v1/triggers.py`

- [ ] **Step 1: Update `_trigger_to_dict()` to include new fields**

Replace the existing `_trigger_to_dict` function:

```python
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
```

- [ ] **Step 2: Update `create_trigger()` to validate wecom_bot type**

In the `create_trigger` function, add validation after the cron validation block:

```python
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
```

- [ ] **Step 3: Add wecom_bot fields to create call**

In the `create_trigger` function, update the `Trigger.create()` call to include new fields:

```python
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
```

- [ ] **Step 4: Skip APScheduler for wecom_bot triggers**

In `create_trigger`, change the scheduler registration block to skip wecom_bot:

```python
    # 注册到调度器 (wecom_bot 类型不需要 APScheduler)
    if t.enabled and t.trigger_type != "wecom_bot":
        await add_job(t)
        t.next_fire_at = await get_next_run_time(t.id)
        await t.save(update_fields=["next_fire_at"])
```

- [ ] **Step 5: Add Redis refresh publish on create/update/delete**

Add a helper function at the top of the file (after imports):

```python
async def _publish_wecom_refresh():
    """发布触发器刷新通知到 Redis"""
    try:
        from core.task_queue import get_task_queue
        tq = get_task_queue()
        await tq.connect()
        await tq._redis.publish("wecom_bot:refresh", "refresh")
    except Exception as e:
        logger.warning(f"Failed to publish wecom refresh: {e}")
```

Then call `_publish_wecom_refresh()` at the end of `create_trigger` (after success response preparation), `update_trigger`, and `delete_trigger` when the trigger type is `wecom_bot`.

- [ ] **Step 6: Update `update_trigger()` to handle wecom_bot fields**

In `update_trigger`, add handling for the new fields after the `notification_id` block:

```python
    if body.wecom_chat_type is not None:
        t.wecom_chat_type = body.wecom_chat_type
        update_fields.append("wecom_chat_type")
    if body.wecom_chat_id is not None:
        t.wecom_chat_id = body.wecom_chat_id
        update_fields.append("wecom_chat_id")
    if body.wecom_user_id is not None:
        t.wecom_user_id = body.wecom_user_id
        update_fields.append("wecom_user_id")
```

And update the scheduler sync block to skip wecom_bot:

```python
    # 同步调度器 (wecom_bot 类型不需要 APScheduler)
    if t.enabled and t.trigger_type != "wecom_bot":
        await reschedule_job(t)
        t.next_fire_at = await get_next_run_time(t.id)
        await t.save(update_fields=["next_fire_at"])
    elif t.trigger_type != "wecom_bot":
        await remove_job(t.id)
        t.next_fire_at = None
        await t.save(update_fields=["next_fire_at"])
```

- [ ] **Step 7: Commit**

```bash
git add backend/api/v1/triggers.py
git commit -m "feat(wecom-bot): update trigger API with wecom_bot validation and Redis refresh"
```

---

### Task B4: Add handshake binding API endpoints

**Files:**
- Modify: `backend/api/v1/triggers.py`

- [ ] **Step 1: Add generate-code endpoint**

Add after the existing `list_trigger_executions` endpoint:

```python
import random
import string


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
    import json as _json
    from core.task_queue import get_task_queue
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
    import json as _json
    from core.task_queue import get_task_queue
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/api/v1/triggers.py
git commit -m "feat(wecom-bot): add handshake binding API endpoints"
```

---

### Task B5: Implement message bridge service

**Files:**
- Create: `backend/core/wecom_bot/message_bridge.py`

- [ ] **Step 1: Create message bridge module**

```python
"""企微机器人消息桥接 — 消息路由 + 工作流执行 + 流式回复

职责：
1. 维护 (chat_type, chat_id) -> trigger 内存映射
2. 接收 aibot 消息回调，匹配触发器
3. 处理验证码匹配逻辑
4. 触发 workflow 执行并流式回复结果
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, Tuple

from loguru import logger


BEIJING_TZ = timezone(timedelta(hours=8))


class WecomBotBridge:
    """消息桥接器"""

    def __init__(self, redis_client):
        self._redis = redis_client
        # (chat_type, chat_id) -> trigger dict
        self._trigger_map: Dict[Tuple[str, str], Dict[str, Any]] = {}

    async def load_mappings(self):
        """从数据库加载所有 wecom_bot 类型的启用触发器"""
        from models.trigger import Trigger

        triggers = await Trigger.filter(
            trigger_type="wecom_bot",
            enabled=True,
        ).select_related("app")

        self._trigger_map.clear()
        for t in triggers:
            if t.wecom_chat_type == "group" and t.wecom_chat_id:
                key = ("group", t.wecom_chat_id)
            elif t.wecom_chat_type == "user" and t.wecom_user_id:
                key = ("user", t.wecom_user_id)
            else:
                logger.warning(f"Trigger {t.id} has invalid wecom config, skipping")
                continue

            self._trigger_map[key] = {
                "id": t.id,
                "name": t.name,
                "app_id": t.app_id,
                "app_enabled": t.app.enabled if t.app else False,
                "message": t.message,
                "wecom_chat_type": t.wecom_chat_type,
            }

        logger.info(f"Loaded {len(self._trigger_map)} wecom_bot trigger mappings")

    async def refresh_mappings(self):
        """刷新触发器映射（由 Redis pub/sub 触发）"""
        logger.info("Refreshing wecom_bot trigger mappings...")
        await self.load_mappings()

    async def handle_message(self, frame: Dict[str, Any], ws_client) -> None:
        """处理收到的 aibot 消息回调"""
        body = frame.get("body", {})
        msgtype = body.get("msgtype", "")
        from_info = body.get("from", {})

        chatid = from_info.get("chatid", "")
        userid = from_info.get("userid", "")

        # 非文本消息，回复提示
        if msgtype != "text":
            if chatid:
                await ws_client.send_message(chatid, {
                    "msgtype": "text",
                    "text": {"content": "Currently only text messages are supported"},
                })
            return

        content = body.get("text", {}).get("content", "").strip()

        # 检查是否是验证码
        if await self._check_verification_code(content, chatid, userid, frame, ws_client):
            return

        # 正常消息路由
        await self._route_message(content, chatid, userid, frame, ws_client)

    async def _check_verification_code(
        self, content: str, chatid: str, userid: str,
        frame: Dict[str, Any], ws_client
    ) -> bool:
        """检查消息是否匹配验证码"""
        # 检查 Redis 中是否有匹配的验证码
        bind_data = await self._redis.get(f"wecom_bind:{content}")
        if not bind_data:
            return False

        # 匹配成功，写入绑定结果
        bind_info = json.loads(bind_data)
        chat_type = "group" if chatid else "user"
        chat_id = chatid if chatid else userid

        await self._redis.set(
            f"wecom_bind_result:{content}",
            json.dumps({"chat_type": chat_type, "chat_id": chat_id}),
            ex=300,
        )

        # 删除验证码（一次性使用）
        await self._redis.delete(f"wecom_bind:{content}")

        logger.info(f"Verification code {content} bound to {chat_type}:{chat_id}")

        # 回复确认消息
        if chatid:
            await ws_client.send_message(chatid, {
                "msgtype": "text",
                "text": {"content": f"Binding successful! Chat ID: {chat_id}"},
            })
        else:
            await ws_client.reply_stream(frame, str(uuid.uuid4()), "Binding successful!", finish=True)

        return True

    async def _route_message(
        self, content: str, chatid: str, userid: str,
        frame: Dict[str, Any], ws_client
    ) -> None:
        """路由消息到匹配的触发器"""
        # 查找匹配的触发器
        trigger_info = None
        if chatid:
            trigger_info = self._trigger_map.get(("group", chatid))
        if not trigger_info and userid:
            trigger_info = self._trigger_map.get(("user", userid))

        if not trigger_info:
            logger.debug(f"No trigger match for chatid={chatid}, userid={userid}")
            return

        if not trigger_info.get("app_enabled"):
            logger.warning(f"Trigger {trigger_info['id']} app is disabled")
            return

        logger.info(f"Message matched trigger {trigger_info['id']} ({trigger_info['name']})")

        # 执行工作流
        await self._execute_workflow(trigger_info, content, frame, ws_client)

    async def _execute_workflow(
        self, trigger_info: Dict[str, Any], user_message: str,
        frame: Dict[str, Any], ws_client
    ) -> None:
        """执行工作流并流式回复"""
        from models.session import Session
        from models.trigger import TriggerExecution
        from core.task_queue import get_task_queue

        trigger_id = trigger_info["id"]
        app_id = trigger_info["app_id"]
        stream_id = str(uuid.uuid4())
        now_bj = datetime.now(BEIJING_TZ).replace(tzinfo=None)

        # 创建 session
        session_id = f"wecom_{trigger_id}_{now_bj.strftime('%Y%m%d%H%M%S')}"
        session = await Session.create(
            id=session_id,
            app_id=app_id,
            user_id="wecom_bot",
            messages=[{"role": "user", "content": user_message}],
            expired_at=now_bj + timedelta(hours=1),
        )

        # 入队任务
        task_queue = get_task_queue()
        task_id = await task_queue.enqueue(
            app_id=app_id,
            session_id=session_id,
            message=user_message,
            stream=True,
        )

        # 写入执行记录
        execution = await TriggerExecution.create(
            trigger_id=trigger_id,
            session_id=session_id,
            task_id=task_id,
            source="auto",
            status="submitted",
        )

        # 订阅流式事件并回复
        accumulated = ""
        try:
            async for event in task_queue.subscribe_events(task_id):
                event_type = event.get("type")

                if event_type == "token":
                    token = event.get("content", "")
                    accumulated += token
                    await ws_client.reply_stream(frame, stream_id, accumulated, finish=False)

                elif event_type == "done":
                    final_content = event.get("content", accumulated)
                    await ws_client.reply_stream(frame, stream_id, final_content, finish=True)
                    execution.status = "success"
                    execution.completed_at = datetime.now(BEIJING_TZ).replace(tzinfo=None)
                    execution.duration_ms = int(
                        (execution.completed_at - execution.started_at).total_seconds() * 1000
                    )
                    await execution.save(update_fields=["status", "completed_at", "duration_ms"])
                    logger.info(f"Workflow completed for trigger {trigger_id}, task {task_id}")
                    return

                elif event_type in ("error", "_abort"):
                    error_msg = event.get("message", "Workflow execution failed")
                    await ws_client.reply_stream(frame, stream_id, f"Error: {error_msg}", finish=True)
                    execution.status = "failed"
                    execution.error_message = error_msg
                    execution.completed_at = datetime.now(BEIJING_TZ).replace(tzinfo=None)
                    await execution.save(update_fields=["status", "error_message", "completed_at"])
                    logger.error(f"Workflow failed for trigger {trigger_id}: {error_msg}")
                    return

        except asyncio.TimeoutError:
            await ws_client.reply_stream(frame, stream_id, "Error: Workflow execution timeout", finish=True)
            execution.status = "failed"
            execution.error_message = "Timeout"
            execution.completed_at = datetime.now(BEIJING_TZ).replace(tzinfo=None)
            await execution.save(update_fields=["status", "error_message", "completed_at"])
            logger.error(f"Workflow timeout for trigger {trigger_id}")

        except Exception as e:
            await ws_client.reply_stream(frame, stream_id, f"Error: {str(e)}", finish=True)
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = datetime.now(BEIJING_TZ).replace(tzinfo=None)
            await execution.save(update_fields=["status", "error_message", "completed_at"])
            logger.error(f"Workflow error for trigger {trigger_id}: {e}")
```

- [ ] **Step 2: Commit**

```bash
git add backend/core/wecom_bot/message_bridge.py
git commit -m "feat(wecom-bot): implement message bridge with routing and streaming reply"
```

---

### Task B6: Implement WS connector main process

**Files:**
- Create: `backend/core/wecom_bot/connector.py`
- Create: `backend/core/wecom_bot/__main__.py`

- [ ] **Step 1: Create connector module**

```python
"""企微机器人 WS 连接器 — 生命周期管理

职责：
1. 从 SysConfig 读取 WECOM_BOT_ID / WECOM_BOT_SECRET
2. 创建 WSClient 并连接
3. 注册消息回调到 WecomBotBridge
4. 监听 Redis pub/sub 刷新触发器映射
"""

import asyncio
import json
from typing import Optional

from loguru import logger
from redis.asyncio import Redis

from core.wecom_bot.aibot_sdk.client import WSClient
from core.wecom_bot.aibot_sdk.types import WSClientOptions
from core.wecom_bot.message_bridge import WecomBotBridge


class WecomBotConnector:
    """WS 连接器"""

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis: Optional[Redis] = None
        self._ws_client: Optional[WSClient] = None
        self._bridge: Optional[WecomBotBridge] = None
        self._running = False

    async def start(self):
        """启动连接器"""
        logger.info("WecomBotConnector starting...")

        # 连接 Redis
        self._redis = await Redis.from_url(
            self._redis_url, decode_responses=True, socket_connect_timeout=5
        )
        logger.info("Redis connected")

        # 加载凭证
        bot_id, bot_secret = await self._load_credentials()
        if not bot_id or not bot_secret:
            logger.warning("Wecom bot credentials not configured, entering retry loop...")
            bot_id, bot_secret = await self._wait_for_credentials()

        # 创建消息桥接器
        self._bridge = WecomBotBridge(self._redis)
        await self._bridge.load_mappings()

        # 创建 WSClient
        options = WSClientOptions(
            bot_id=bot_id,
            secret=bot_secret,
            max_reconnect_attempts=-1,  # 无限重连
        )
        self._ws_client = WSClient(options)

        # 注册事件回调
        self._ws_client.on("authenticated", self._on_authenticated)
        self._ws_client.on("message", self._on_message)
        self._ws_client.on("error", self._on_error)
        self._ws_client.on("disconnected", self._on_disconnected)

        # 连接
        self._running = True
        await self._ws_client.connect()

        # 启动 Redis pub/sub 监听
        asyncio.create_task(self._listen_refresh())

        logger.info("WecomBotConnector started successfully")

    async def _load_credentials(self):
        """从数据库加载凭证"""
        from models.sys_config import SysConfig

        bot_id_config = await SysConfig.get_or_none(config_key="WECOM_BOT_ID")
        bot_secret_config = await SysConfig.get_or_none(config_key="WECOM_BOT_SECRET")

        bot_id = bot_id_config.config_value if bot_id_config else ""
        bot_secret = bot_secret_config.config_value if bot_secret_config else ""

        return bot_id, bot_secret

    async def _wait_for_credentials(self):
        """等待凭证配置（每 30 秒重试）"""
        while True:
            await asyncio.sleep(30)
            bot_id, bot_secret = await self._load_credentials()
            if bot_id and bot_secret:
                logger.info("Wecom bot credentials found!")
                return bot_id, bot_secret
            logger.debug("Still waiting for wecom bot credentials...")

    def _on_authenticated(self):
        """认证成功回调"""
        logger.info("Wecom bot authenticated successfully")

    def _on_message(self, frame):
        """消息回调"""
        if self._bridge:
            asyncio.ensure_future(self._bridge.handle_message(frame, self._ws_client))

    def _on_error(self, error):
        """错误回调"""
        logger.error(f"Wecom bot error: {error}")

    def _on_disconnected(self, reason):
        """断开连接回调"""
        logger.warning(f"Wecom bot disconnected: {reason}")

    async def _listen_refresh(self):
        """监听 Redis pub/sub 刷新触发器映射"""
        pubsub = self._redis.pubsub()
        await pubsub.subscribe("wecom_bot:refresh")

        try:
            while self._running:
                message = await pubsub.get_message(
                    timeout=1.0, ignore_subscribe_messages=True
                )
                if message and message.get("type") == "message":
                    if self._bridge:
                        await self._bridge.refresh_mappings()
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe("wecom_bot:refresh")
            await pubsub.close()

    async def stop(self):
        """停止连接器"""
        self._running = False
        if self._ws_client:
            self._ws_client.disconnect()
        if self._redis:
            await self._redis.close()
        logger.info("WecomBotConnector stopped")
```

- [ ] **Step 2: Create `__main__.py` entry point**

```python
"""企微机器人 WS 连接器 — 独立进程入口

运行方式:
  PYTHONPATH=backend python -m backend.core.wecom_bot

环境变量:
  DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME  — 数据库连接
  REDIS_URL  — Redis 连接
  USE_SQLITE=1  — 使用 SQLite（开发模式）
"""

import asyncio
import signal
import sys
from pathlib import Path

from loguru import logger

# 确保 backend 在 Python path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config import settings, TORTOISE_ORM
from tortoise import Tortoise


async def main():
    logger.info("=" * 50)
    logger.info("Wecom Bot Connector starting...")
    logger.info(f"  DB={settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    logger.info(f"  REDIS={settings.REDIS_URL}")
    logger.info("=" * 50)

    # 初始化数据库
    await Tortoise.init(config=TORTOISE_ORM)
    logger.info("Database connected")

    # 启动连接器
    from core.wecom_bot.connector import WecomBotConnector
    connector = WecomBotConnector(settings.REDIS_URL)
    await connector.start()

    # 等待退出信号
    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Received shutdown signal")
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    logger.info("Wecom Bot Connector ready, waiting for messages...")
    await stop_event.wait()

    # 清理
    await connector.stop()
    await Tortoise.close_connections()
    logger.info("Wecom Bot Connector stopped")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Commit**

```bash
git add backend/core/wecom_bot/connector.py backend/core/wecom_bot/__main__.py
git commit -m "feat(wecom-bot): implement WS connector and process entry point"
```

---

### Task B7: Add Docker configuration

**Files:**
- Create: `Dockerfile.wecom-bot`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Create Dockerfile.wecom-bot**

```dockerfile
# ============================================
# 企微机器人 WS 连接器
# ============================================
FROM python:3.11-slim

LABEL app="hh-agent-hub-wecom-bot"
LABEL description="WeCom Bot WebSocket Connector"

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmariadb-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制源码
COPY backend/ ./backend/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

CMD ["python", "-m", "backend.core.wecom_bot"]
```

- [ ] **Step 2: Add wecom-bot service to docker-compose.yml**

Add the following service block in `docker-compose.yml` after the `worker` service:

```yaml
  # ============================================
  # 企微机器人 WS 连接器
  # ============================================
  wecom-bot:
    build:
      context: .
      dockerfile: Dockerfile.wecom-bot
    environment:
      - DB_HOST=mysql
      - DB_PORT=3306
      - DB_USER=${DB_USER:-agent_platform}
      - DB_PASSWORD=${DB_PASSWORD:-changeme}
      - DB_NAME=${DB_NAME:-agent_platform}
      - REDIS_URL=redis://redis:6379/0
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped
    networks:
      - agent-net
```

- [ ] **Step 3: Commit**

```bash
git add Dockerfile.wecom-bot docker-compose.yml
git commit -m "feat(wecom-bot): add Docker configuration for wecom-bot container"
```

---

## Frontend Tasks

### Task F1: Add wecom-bot API methods

**Files:**
- Modify: `frontend/src/api/triggers.ts`

- [ ] **Step 1: Add new API methods**

```typescript
import client from './client'

export const triggersApi = {
  list: () => client.get('/triggers'),
  get: (id: number) => client.get(`/triggers/${id}`),
  create: (data: any) => client.post('/triggers', data),
  update: (id: number, data: any) => client.put(`/triggers/${id}`, data),
  delete: (id: number) => client.delete(`/triggers/${id}`),
  execute: (id: number) => client.post(`/triggers/${id}/execute`),
  executions: (id: number, params?: { page?: number; page_size?: number }) =>
    client.get(`/triggers/${id}/executions`, { params }),
  // NEW: wecom-bot binding
  generateCode: (app_id: number) => client.post('/triggers/wecom-bot/generate-code', { app_id }),
  getBindStatus: (code: string) => client.get(`/triggers/wecom-bot/bind-status/${code}`),
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/triggers.ts
git commit -m "feat(wecom-bot): add frontend API methods for binding"
```

---

### Task F2: Update TriggerEditor with wecom_bot type support

**Files:**
- Modify: `frontend/src/views/TriggerEditor.vue`

- [ ] **Step 1: Add wecom_bot radio option**

In the `a-radio-group` for trigger_type, add a third radio:

```vue
<a-radio-group v-model:value="form.trigger_type">
  <a-radio value="interval">间隔触发</a-radio>
  <a-radio value="cron">Cron 表达式</a-radio>
  <a-radio value="wecom_bot">企微机器人</a-radio>
</a-radio-group>
```

- [ ] **Step 2: Add wecom_bot binding step UI**

After the notification channel select and before the submit button, add the wecom_bot binding section:

```vue
<!-- 企微机器人绑定 -->
<template v-if="form.trigger_type === 'wecom_bot'">
  <a-divider>企微机器人绑定</a-divider>

  <!-- Step 1: 选择应用已通过通用 app_id 字段完成 -->

  <!-- Step 2: 生成验证码并绑定 -->
  <a-form-item v-if="!bindResult" label="绑定聊天">
    <a-space direction="vertical" class="w-full">
      <a-button
        type="dashed"
        @click="handleGenerateCode"
        :loading="generatingCode"
        :disabled="!form.app_id"
      >
        生成绑定验证码
      </a-button>

      <template v-if="bindCode">
        <a-alert type="info" show-icon>
          <template #message>
            <div>请在企业微信的群聊或私聊中，向智能机器人发送以下验证码：</div>
            <div class="text-2xl font-bold tracking-widest my-2">{{ bindCode }}</div>
            <div class="text-gray-400">验证码有效期 5 分钟，等待绑定中...</div>
          </template>
        </a-alert>
      </template>
    </a-space>
  </a-form-item>

  <!-- Step 3: 绑定结果 -->
  <a-form-item v-if="bindResult" label="绑定结果">
    <a-alert type="success" show-icon>
      <template #message>
        <div>绑定成功！</div>
        <div>聊天类型：{{ bindResult.chat_type === 'group' ? '群聊' : '私聊' }}</div>
        <div>聊天ID：{{ bindResult.chat_id }}</div>
      </template>
    </a-alert>
  </a-form-item>

  <!-- 绑定后的隐藏字段 -->
  <input type="hidden" :value="bindResult?.chat_type" />
  <input type="hidden" :value="bindResult?.chat_id" />
</template>
```

- [ ] **Step 3: Add script logic for binding flow**

Add to the `<script setup>` section:

```typescript
import { ref, onUnmounted } from 'vue'

// NEW: wecom-bot binding state
const bindCode = ref('')
const bindResult = ref<{ chat_type: string; chat_id: string } | null>(null)
const generatingCode = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

async function handleGenerateCode() {
  if (!form.value.app_id) {
    message.warning('请先选择关联应用')
    return
  }
  generatingCode.value = true
  try {
    const res = await triggersApi.generateCode(form.value.app_id)
    const data = res.data.data
    bindCode.value = data.code
    // 开始轮询绑定状态
    startPolling(data.code)
  } catch (e: any) {
    message.error(e.response?.data?.message || '生成验证码失败')
  } finally {
    generatingCode.value = false
  }
}

function startPolling(code: string) {
  if (pollTimer) clearInterval(pollTimer)
  let attempts = 0
  pollTimer = setInterval(async () => {
    attempts++
    if (attempts > 60) { // 5分钟超时
      clearInterval(pollTimer!)
      pollTimer = null
      message.error('绑定超时，请重新生成验证码')
      bindCode.value = ''
      return
    }
    try {
      const res = await triggersApi.getBindStatus(code)
      const data = res.data.data
      if (data.status === 'bound') {
        clearInterval(pollTimer!)
        pollTimer = null
        bindResult.value = {
          chat_type: data.chat_type,
          chat_id: data.chat_id,
        }
        // 自动填充表单字段
        form.value.wecom_chat_type = data.chat_type
        if (data.chat_type === 'group') {
          form.value.wecom_chat_id = data.chat_id
        } else {
          form.value.wecom_user_id = data.chat_id
        }
        message.success('绑定成功！')
      }
    } catch (e) {
      // 404 = 已过期
      if ((e as any).response?.status === 404) {
        clearInterval(pollTimer!)
        pollTimer = null
        message.error('验证码已过期，请重新生成')
        bindCode.value = ''
      }
    }
  }, 5000) // 每 5 秒轮询
}

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
```

- [ ] **Step 4: Update form initialization for wecom_bot fields**

Add to the form ref:

```typescript
const form = ref({
  name: '',
  description: '',
  trigger_type: 'interval' as 'interval' | 'cron' | 'wecom_bot',
  interval_value: undefined as number | undefined,
  interval_unit: undefined as string | undefined,
  cron_expression: '',
  app_id: undefined as number | undefined,
  message: '',
  notification_id: undefined as number | undefined,
  // NEW: wecom_bot fields
  wecom_chat_type: undefined as string | undefined,
  wecom_chat_id: undefined as string | undefined,
  wecom_user_id: undefined as string | undefined,
})
```

- [ ] **Step 5: Update submit handler to clean wecom_bot fields**

In `handleSubmit`, add cleanup for wecom_bot type:

```typescript
async function handleSubmit() {
  submitting.value = true
  try {
    const payload: Record<string, any> = { ...form.value }
    // 清理互斥字段
    if (payload.trigger_type === 'interval') {
      payload.cron_expression = null
      payload.wecom_chat_type = null
      payload.wecom_chat_id = null
      payload.wecom_user_id = null
    } else if (payload.trigger_type === 'cron') {
      payload.interval_value = null
      payload.interval_unit = null
      payload.wecom_chat_type = null
      payload.wecom_chat_id = null
      payload.wecom_user_id = null
    } else if (payload.trigger_type === 'wecom_bot') {
      payload.interval_value = null
      payload.interval_unit = null
      payload.cron_expression = null
      payload.notification_id = null
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
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/TriggerEditor.vue
git commit -m "feat(wecom-bot): add wecom_bot trigger type with multi-step binding UI"
```

---

### Task F3: Update TriggerList display

**Files:**
- Modify: `frontend/src/views/TriggerList.vue`

- [ ] **Step 1: Add wecom_bot type badge**

Find the trigger type tag/badge display and add a case for `wecom_bot`:

```vue
<a-tag :color="triggerTypeColor(record.trigger_type)">
  {{ triggerTypeLabel(record.trigger_type) }}
</a-tag>
```

Add helper functions:

```typescript
function triggerTypeColor(type: string) {
  const map: Record<string, string> = {
    interval: 'blue',
    cron: 'green',
    wecom_bot: 'purple',
  }
  return map[type] || 'default'
}

function triggerTypeLabel(type: string) {
  const map: Record<string, string> = {
    interval: '间隔触发',
    cron: 'Cron触发',
    wecom_bot: '企微机器人',
  }
  return map[type] || type
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/TriggerList.vue
git commit -m "feat(wecom-bot): add wecom_bot type badge to trigger list"
```

---

## API Test Tasks

### Task A1: Test handshake binding API

**Dependencies:** B3, B4

- [ ] **Step 1: Test generate-code endpoint**

```
POST /api/v1/triggers/wecom-bot/generate-code
Body: {"app_id": 1}
Expected: {"code": 0, "data": {"code": "XXXXXX", "expires_in": 300}}
```

- [ ] **Step 2: Test generate-code with invalid app_id**

```
POST /api/v1/triggers/wecom-bot/generate-code
Body: {"app_id": 99999}
Expected: {"code": 400, "message": "应用不存在"}
```

- [ ] **Step 3: Test bind-status polling (pending)**

```
GET /api/v1/triggers/wecom-bot/bind-status/{code}
Expected: {"code": 0, "data": {"status": "pending"}}
```

- [ ] **Step 4: Test bind-status with expired code**

```
GET /api/v1/triggers/wecom-bot/bind-status/XXXXXX
Expected: {"code": 404, "message": "验证码不存在或已过期"}
```

---

### Task A2: Test trigger CRUD with wecom_bot type

**Dependencies:** B2, B3

- [ ] **Step 1: Test create wecom_bot trigger (group)**

```
POST /api/v1/triggers
Body: {
  "name": "Test Group Bot",
  "trigger_type": "wecom_bot",
  "app_id": 1,
  "message": "Hello",
  "wecom_chat_type": "group",
  "wecom_chat_id": "group123"
}
Expected: {"code": 0, "data": {"trigger_type": "wecom_bot", "wecom_chat_type": "group", "wecom_chat_id": "group123"}}
```

- [ ] **Step 2: Test create wecom_bot trigger (user)**

```
POST /api/v1/triggers
Body: {
  "name": "Test User Bot",
  "trigger_type": "wecom_bot",
  "app_id": 1,
  "message": "Hello",
  "wecom_chat_type": "user",
  "wecom_user_id": "user456"
}
Expected: {"code": 0, "data": {"trigger_type": "wecom_bot", "wecom_chat_type": "user", "wecom_user_id": "user456"}}
```

- [ ] **Step 3: Test create wecom_bot trigger without wecom_chat_type (should fail)**

```
POST /api/v1/triggers
Body: {
  "name": "Test Invalid",
  "trigger_type": "wecom_bot",
  "app_id": 1,
  "message": "Hello"
}
Expected: {"code": 400, "message": "wecom_bot 类型必须指定 wecom_chat_type"}
```

- [ ] **Step 4: Test trigger list includes wecom_bot fields**

```
GET /api/v1/triggers
Expected: Array containing objects with wecom_chat_type, wecom_chat_id, wecom_user_id fields
```

- [ ] **Step 5: Test update wecom_bot trigger**

```
PUT /api/v1/triggers/{id}
Body: {"wecom_chat_id": "new_group_789"}
Expected: {"code": 0, "data": {"wecom_chat_id": "new_group_789"}}
```

---

### Task A3: Test message routing and streaming (integration)

**Dependencies:** B5, B6

- [ ] **Step 1: Verify wecom-bot container starts and connects**

Check Docker logs:
```bash
docker compose logs wecom-bot
Expected: "WecomBotConnector started successfully" or "credentials not configured"
```

- [ ] **Step 2: Verify trigger mappings loaded**

```bash
docker compose logs wecom-bot | grep "Loaded"
Expected: "Loaded N wecom_bot trigger mappings"
```

- [ ] **Step 3: End-to-end message flow test**

Manual test: Send a message in the bound WeCom chat and verify:
1. Message is received by the connector
2. Trigger is matched
3. Workflow is executed
4. Streaming reply is sent back via the bot

---

## Commit Sequence Summary

| Commit | Description |
|--------|-------------|
| B1 | feat(wecom-bot): integrate aibot SDK and add dependencies |
| B2 | feat(wecom-bot): extend Trigger model and schemas with wecom_bot fields |
| B3 | feat(wecom-bot): update trigger API with wecom_bot validation and Redis refresh |
| B4 | feat(wecom-bot): add handshake binding API endpoints |
| B5 | feat(wecom-bot): implement message bridge with routing and streaming reply |
| B6 | feat(wecom-bot): implement WS connector and process entry point |
| B7 | feat(wecom-bot): add Docker configuration for wecom-bot container |
| F1 | feat(wecom-bot): add frontend API methods for binding |
| F2 | feat(wecom-bot): add wecom_bot trigger type with multi-step binding UI |
| F3 | feat(wecom-bot): add wecom_bot type badge to trigger list |
