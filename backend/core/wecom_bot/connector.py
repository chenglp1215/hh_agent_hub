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
