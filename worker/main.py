"""
Worker 服务入口 — 后台任务处理

职责：
1. 消费 Redis 任务队列，执行 LangGraph 工作流
2. 运行 Claude Code Agent 子进程
3. 定时清理过期 session workspace

与 main 容器共享 workspace_data 卷，路径统一为 /data/workflow_workspaces。
"""

import asyncio
import signal
import sys
from pathlib import Path

from loguru import logger
from tortoise import Tortoise

# 确保 backend 在 Python path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings, TORTOISE_ORM
from core.task_queue import TaskQueue, get_task_queue
from core.session_manager import session_manager
from core.agent_call_log import agent_call_logger  # noqa: F401 — 触发单例初始化


import uuid

WORKER_ID = f"worker_{uuid.uuid4().hex[:8]}"


async def heartbeat_loop(task_queue: TaskQueue):
    """每 10 秒写一次心跳到 Redis"""
    while True:
        try:
            await task_queue._redis.set(f"worker:heartbeat:{WORKER_ID}", "1", ex=30)
        except Exception:
            pass
        await asyncio.sleep(10)


async def on_shutdown():
    logger.info("Worker shutting down, closing connections...")
    tq = get_task_queue()
    try:
        await tq._redis.delete(f"worker:heartbeat:{WORKER_ID}")
    except Exception:
        pass
    await tq.disconnect()
    await Tortoise.close_connections()


async def consumer_loop(task_queue: TaskQueue):
    """消费任务队列：循环 BRPOP，构建并执行工作流"""
    logger.info("[Consumer] Starting task consumer loop")
    from core.workflow_executor import execute_task

    while True:
        try:
            task = await task_queue.dequeue(timeout=10)
            if task is None:
                continue  # 超时，继续循环

            logger.info(
                f"[Consumer] Processing task {task['task_id']} "
                f"session={task['session_id']} stream={task.get('stream')}"
            )
            await execute_task(task, task_queue)

        except asyncio.CancelledError:
            logger.info("[Consumer] Consumer cancelled")
            break
        except Exception as e:
            logger.error(f"[Consumer] Fatal error: {e}")
            await asyncio.sleep(5)


async def main():
    logger.info("=" * 50)
    logger.info("Worker starting...")
    logger.info(f"  WORKSPACE_BASE={settings.WORKSPACE_BASE}")
    logger.info(f"  DB={settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    logger.info(f"  REDIS={settings.REDIS_URL}")
    logger.info("=" * 50)

    # Init DB
    await Tortoise.init(config=TORTOISE_ORM)
    logger.info("Worker DB connected")

    # Init TaskQueue
    task_queue = get_task_queue(settings.REDIS_URL)
    await task_queue.connect()
    logger.info("Worker TaskQueue connected")

    # ── 后台任务 ──

    # Task 1: 消费工作流任务队列
    consumer_task = asyncio.create_task(consumer_loop(task_queue))

    # Task 2: 定时清理过期 session workspace（每10分钟）
    cleanup_task = asyncio.create_task(session_manager.start_cleanup_task(600))
    logger.info("[Task] Session workspace cleanup started (interval=600s)")

    # Task 3: Worker 心跳（每 10 秒）
    hb_task = asyncio.create_task(heartbeat_loop(task_queue))
    logger.info(f"[Task] Worker heartbeat started (id={WORKER_ID})")

    # ── 等待退出信号 ──
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

    logger.info("Worker ready, waiting for tasks...")
    await stop_event.wait()

    # ── 清理 ──
    consumer_task.cancel()
    cleanup_task.cancel()
    hb_task.cancel()
    await on_shutdown()
    logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
