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
