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
