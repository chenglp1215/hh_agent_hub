"""Redis 任务队列 — main 与 worker 之间的异步任务通信

职责：
  main (enqueue)  →   LPUSH workflow:queue
  worker (dequeue) →  BRPOP workflow:queue
  worker (publish)  →  SET workflow:result:{task_id}
                      + PUBLISH workflow:events:{task_id}

Key 命名约定：
  workflow:queue              List    — 任务队列
  workflow:result:{task_id}    String  — 最终结果（1h 过期）
  workflow:events:{task_id}    PubSub  — 流式事件
"""

import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

from redis.asyncio import Redis
from loguru import logger


class TaskQueue:
    QUEUE_KEY = "workflow:queue"
    RESULT_PREFIX = "workflow:result:"
    EVENTS_PREFIX = "workflow:events:"

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis: Optional[Redis] = None

    async def connect(self):
        """建立 Redis 连接"""
        if not self._redis:
            self._redis = await Redis.from_url(
                self.redis_url, decode_responses=True, socket_connect_timeout=5
            )
            logger.info(f"TaskQueue connected to {self.redis_url}")

    async def disconnect(self):
        if self._redis:
            await self._redis.close()
            self._redis = None

    # ── producer (main) ──────────────────────────────────────────

    async def enqueue(self, app_id: int, session_id: str,
                      message: str, stream: bool = False) -> str:
        """将任务加入队列

        Returns:
            task_id: 任务标识，主流程据此获取结果
        """
        await self.connect()
        task_id = str(uuid.uuid4())
        task = {
            "task_id": task_id,
            "session_id": session_id,
            "app_id": app_id,
            "message": message,
            "stream": stream,
            "created_at": datetime.now().isoformat(),
        }
        await self._redis.lpush(self.QUEUE_KEY, json.dumps(task, ensure_ascii=False))
        logger.info(f"Enqueued task {task_id} for session {session_id} (stream={stream})")
        return task_id

    async def get_result(self, task_id: str, timeout: float = 120) -> Optional[Dict[str, Any]]:
        """轮询等待任务结果

        通过 Redis pub/sub 等待结果信号，避免忙轮询。
        """
        await self.connect()
        pubsub = self._redis.pubsub()
        result_channel = f"{self.RESULT_PREFIX}{task_id}"
        await pubsub.subscribe(result_channel)

        try:
            # 先查一次（可能 worker 已经完成）
            data = await self._redis.get(f"{self.RESULT_PREFIX}{task_id}")
            if data:
                return json.loads(data)

            # 等待 pub/sub 通知
            deadline = datetime.now().timestamp() + timeout
            while datetime.now().timestamp() < deadline:
                message = await pubsub.get_message(
                    timeout=min(5, deadline - datetime.now().timestamp()),
                    ignore_subscribe_messages=True,
                )
                if message and message.get("type") == "message":
                    data = await self._redis.get(f"{self.RESULT_PREFIX}{task_id}")
                    if data:
                        return json.loads(data)
        finally:
            await pubsub.unsubscribe(result_channel)
            await pubsub.reset()

        logger.warning(f"Task {task_id} result timeout after {timeout}s")
        return None

    async def subscribe_events(self, task_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """订阅任务的流式事件（用于 SSE）

        Yields:
            dict 事件字典，包含 type 字段
        """
        await self.connect()
        pubsub = self._redis.pubsub()
        events_channel = f"{self.EVENTS_PREFIX}{task_id}"
        await pubsub.subscribe(events_channel)

        try:
            while True:
                message = await pubsub.get_message(
                    timeout=1.0, ignore_subscribe_messages=True
                )
                if message and message.get("type") == "message":
                    data = json.loads(message["data"])
                    yield data
                    if data.get("type") in ("done", "error", "_abort"):
                        return
        finally:
            await pubsub.unsubscribe(events_channel)
            await pubsub.reset()

    # ── consumer (worker) ────────────────────────────────────────

    async def dequeue(self, timeout: int = 10) -> Optional[Dict[str, Any]]:
        """阻塞等待任务

        Args:
            timeout: BRPOP 超时秒数

        Returns:
            task dict 或 None（超时）
        """
        await self.connect()
        result = await self._redis.brpop(self.QUEUE_KEY, timeout=timeout)
        if result:
            task = json.loads(result[1])
            logger.info(f"Dequeued task {task['task_id']} for session {task['session_id']}")
            return task
        return None

    async def publish_event(self, task_id: str, event_type: str, **kwargs):
        """发布流式事件"""
        await self._redis.publish(
            f"{self.EVENTS_PREFIX}{task_id}",
            json.dumps({"type": event_type, **kwargs}, ensure_ascii=False),
        )

    async def publish_result(self, task_id: str, result: Dict[str, Any]):
        """写入最终结果并通知订阅者"""
        result_key = f"{self.RESULT_PREFIX}{task_id}"
        await self._redis.set(result_key, json.dumps(result, ensure_ascii=False), ex=3600)
        await self._redis.publish(result_key, "done")
        logger.info(f"Published result for task {task_id}")


# 全局单例
task_queue: Optional[TaskQueue] = None


def get_task_queue(redis_url: str = None) -> TaskQueue:
    """获取/初始化全局 TaskQueue 实例"""
    global task_queue
    if task_queue is None:
        from config import settings
        task_queue = TaskQueue(redis_url or settings.REDIS_URL)
    return task_queue
