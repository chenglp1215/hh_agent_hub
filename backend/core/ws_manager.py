from fastapi import WebSocket
from typing import Dict, Set
import asyncio
from loguru import logger


class WorkflowWebSocketManager:
    """工作流执行 WebSocket 管理器"""

    def __init__(self):
        self._subscribers: Dict[str, Set[WebSocket]] = {}

    async def subscribe(self, execution_id: str, ws: WebSocket):
        await ws.accept()
        self._subscribers.setdefault(execution_id, set()).add(ws)
        logger.info(f"WebSocket subscribed to {execution_id}")

    def unsubscribe(self, execution_id: str, ws: WebSocket):
        subs = self._subscribers.get(execution_id)
        if subs:
            subs.discard(ws)
            if not subs:
                del self._subscribers[execution_id]

    async def push(self, execution_id: str, event: dict):
        """推送事件到所有订阅该 execution 的客户端"""
        subs = self._subscribers.get(execution_id, set())
        dead = set()
        for ws in subs:
            try:
                await ws.send_json(event)
            except Exception:
                dead.add(ws)
        subs -= dead

    async def broadcast(self, event: dict):
        """广播到所有订阅者"""
        for execution_id in list(self._subscribers.keys()):
            await self.push(execution_id, event)


ws_manager = WorkflowWebSocketManager()
