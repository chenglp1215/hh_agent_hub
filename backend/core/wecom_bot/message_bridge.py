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


def _now_naive() -> datetime:
    """返回北京时间 naive datetime（与数据库存储一致）"""
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)


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

    @staticmethod
    def _strip_at_mention(content: str) -> str:
        """清理消息中的 @机器人名

        群聊中 @机器人 发消息时，企微会在消息开头或末尾附加 @机器人名。
        例如: "@运营服务研发智能机器人 你好" → "你好"
        例如: "7I6P85@运营服务研发智能机器人 " → "7I6P85"
        """
        import re
        # 清理开头的 @xxx（含空格）
        cleaned = re.sub(r'^@[^\s@]+\s*', '', content)
        # 清理末尾的 @xxx（含空格）
        cleaned = re.sub(r'\s*@[^\s@]+\s*$', '', cleaned)
        return cleaned.strip()

    async def handle_message(self, frame: Dict[str, Any], ws_client) -> None:
        """处理收到的 aibot 消息回调"""
        body = frame.get("body", {})
        msgtype = body.get("msgtype", "")
        from_info = body.get("from", {})

        # chatid 在 body 顶层（群聊）或 from 中（私聊）
        chatid = body.get("chatid", "") or from_info.get("chatid", "")
        userid = from_info.get("userid", "")

        logger.info(f"Received message: msgtype={msgtype}, chatid={chatid}, userid={userid}")

        # 非文本消息，回复提示
        if msgtype != "text":
            if chatid or userid:
                await self._reply_text(ws_client, frame, chatid, userid,
                    "暂仅支持文本消息")
            return

        content = body.get("text", {}).get("content", "").strip()
        # 群聊 @机器人 时，消息可能带 @机器人名 前缀或后缀
        content = self._strip_at_mention(content)
        logger.info(f"Text content (cleaned): '{content}'")

        # 检查是否是验证码
        if await self._check_verification_code(content, chatid, userid, frame, ws_client):
            return

        # 正常消息路由
        await self._route_message(content, chatid, userid, frame, ws_client)

    async def _reply_text(self, ws_client, frame, chatid, userid, text):
        """统一回复文本消息"""
        if chatid:
            await ws_client.send_message(chatid, {
                "msgtype": "text",
                "text": {"content": text},
            })
        else:
            await ws_client.reply_stream(frame, str(uuid.uuid4()), text, finish=True)

    async def _check_verification_code(
        self, content: str, chatid: str, userid: str,
        frame: Dict[str, Any], ws_client
    ) -> bool:
        """检查消息是否匹配验证码"""
        # 验证码格式：6位大写字母+数字，先做基本格式检查
        if len(content) != 6 or not content.isalnum():
            logger.debug(f"Content '{content}' is not verification code format (len={len(content)})")
            return False

        # 检查 Redis 中是否有匹配的验证码
        redis_key = f"wecom_bind:{content}"
        bind_data = await self._redis.get(redis_key)
        logger.info(f"Checking verification code '{content}': redis_key={redis_key}, found={bool(bind_data)}")

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
        await self._redis.delete(redis_key)

        logger.info(f"Verification code '{content}' bound to {chat_type}:{chat_id}")

        # 回复确认消息
        await self._reply_text(ws_client, frame, chatid, userid,
            f"绑定成功！\n聊天类型: {'群聊' if chat_type == 'group' else '私聊'}\n聊天ID: {chat_id}")

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
            logger.info(f"No trigger match for chatid={chatid}, userid={userid}, sending help message")
            await self._reply_text(ws_client, frame, chatid, userid,
                "该聊天尚未绑定应用触发器。\n\n"
                "请在管理平台创建企微机器人触发器并完成绑定后，再发送消息。")
            return

        if not trigger_info.get("app_enabled"):
            logger.warning(f"Trigger {trigger_info['id']} app is disabled")
            await self._reply_text(ws_client, frame, chatid, userid,
                "关联的应用已禁用，请联系管理员。")
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
        now_bj = _now_naive()

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

        logger.info(f"Workflow enqueued: trigger={trigger_id}, task={task_id}, session={session_id}")

        # 先回复"正在思考"（finish=False，后续用最终回复覆盖）
        await ws_client.reply_stream(frame, stream_id, "正在思考...", finish=False)

        # 等待工作流结果
        try:
            result = await task_queue.get_result(task_id, timeout=300)

            if result:
                final_answer = result.get("final_answer", "")
                error = result.get("error")

                if error:
                    await ws_client.reply_stream(frame, stream_id, f"Error: {error}", finish=True)
                    execution.status = "failed"
                    execution.error_message = error
                    execution.completed_at = _now_naive()
                    await execution.save(update_fields=["status", "error_message", "completed_at"])
                    logger.error(f"Workflow failed for trigger {trigger_id}: {error}")
                elif final_answer:
                    # 用最终回复覆盖"正在思考..."
                    await ws_client.reply_stream(frame, stream_id, final_answer, finish=True)
                    execution.status = "success"
                    execution.completed_at = _now_naive()
                    started = execution.started_at
                    if started.tzinfo is not None:
                        started = started.astimezone(BEIJING_TZ).replace(tzinfo=None)
                    execution.duration_ms = int(
                        (execution.completed_at - started).total_seconds() * 1000
                    )
                    await execution.save(update_fields=["status", "completed_at", "duration_ms"])
                    logger.info(f"Workflow completed for trigger {trigger_id}, task {task_id}, answer_len={len(final_answer)}")
                else:
                    await ws_client.reply_stream(frame, stream_id, "Error: 工作流未返回结果", finish=True)
                    execution.status = "failed"
                    execution.error_message = "Empty result"
                    execution.completed_at = _now_naive()
                    await execution.save(update_fields=["status", "error_message", "completed_at"])
                    logger.error(f"Workflow empty result for trigger {trigger_id}")
            else:
                await ws_client.reply_stream(frame, stream_id, "Error: 工作流执行超时 (5 min)", finish=True)
                execution.status = "failed"
                execution.error_message = "Timeout"
                execution.completed_at = _now_naive()
                await execution.save(update_fields=["status", "error_message", "completed_at"])
                logger.error(f"Workflow timeout for trigger {trigger_id}")

        except Exception as e:
            await ws_client.reply_stream(frame, stream_id, f"Error: {str(e)}", finish=True)
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = _now_naive()
            await execution.save(update_fields=["status", "error_message", "completed_at"])
            logger.error(f"Workflow error for trigger {trigger_id}: {e}")
