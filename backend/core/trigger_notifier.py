"""触发器执行结果通知 — 企业微信 Webhook"""

import httpx
from loguru import logger


async def send_trigger_notification(trigger, execution):
    """发送触发器执行结果到配置的通知渠道

    fire-and-forget 调用，失败不影响主流程。
    """
    try:
        if not trigger.notification_id:
            return

        await trigger.fetch_related("notification")
        channel = trigger.notification
        if not channel or not channel.enabled:
            return

        # 查询 ChatLog 获取执行结果
        from models.chat_log import ChatLog
        chat_log = await ChatLog.filter(session_id=execution.session_id).first()

        final_answer = ""
        duration_text = ""
        if chat_log:
            final_answer = chat_log.final_answer or "(无输出)"
            if len(final_answer) > 500:
                final_answer = final_answer[:500] + "..."
            if chat_log.duration_ms:
                duration_text = f"{chat_log.duration_ms}ms"

        if execution.duration_ms and not duration_text:
            duration_text = f"{execution.duration_ms}ms"

        source_text = "定时触发" if execution.source == "auto" else "手动执行"
        status_text = {"submitted": "已提交", "success": "成功", "failed": "失败"}.get(
            execution.status, execution.status
        )
        status_emoji = {"success": "✅", "failed": "❌", "submitted": "⏳"}.get(
            execution.status, "📋"
        )

        # 构建企业微信 markdown 消息
        md_content = (
            f"## {status_emoji} 触发器执行通知\n\n"
            f"> **触发器**: {trigger.name}\n"
            f"> **来源**: {source_text}\n"
            f"> **状态**: {status_text}\n"
        )
        if duration_text:
            md_content += f"> **耗时**: {duration_text}\n"
        if execution.error_message:
            md_content += f"\n**错误信息**:\n{execution.error_message}\n"
        elif final_answer:
            md_content += f"\n**执行结果**:\n{final_answer}\n"

        payload = {
            "msgtype": "markdown",
            "markdown": {"content": md_content},
        }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(channel.webhook_url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            if result.get("errcode", 0) != 0:
                logger.warning(f"Webhook response error: {result}")
            else:
                logger.info(f"Notification sent for trigger {trigger.id}, execution {execution.id}")

        # 标记已通知
        execution.notified = True
        await execution.save(update_fields=["notified"])

    except Exception as e:
        logger.error(f"Failed to send notification for trigger {trigger.id}: {e}")
