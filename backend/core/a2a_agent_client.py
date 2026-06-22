import httpx
from typing import Dict, Any
from loguru import logger
from google.protobuf.json_format import ParseDict
from a2a.types import a2a_pb2
from a2a.client.client import ClientConfig
from a2a.client.client_factory import create_client


class A2AAgentClient:
    """A2A Agent 客户端 — 通过 A2A 协议与对端 Agent 通信

    流程：
    1. 从 agent_card_url 获取 Agent Card
    2. 通过 A2A SDK 创建客户端
    3. 发送消息并收集流式响应
    """

    def __init__(self, a2a_config: Dict[str, Any]):
        self.agent_card_url = a2a_config.get("agent_card_url", "").rstrip("/")
        self.headers = a2a_config.get("headers", {}) or {}
        self.timeout = a2a_config.get("timeout", 30)
        self._card = None

    async def _fetch_agent_card(self) -> a2a_pb2.AgentCard:
        """获取并缓存 Agent Card"""
        if self._card is not None:
            return self._card

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                resp = await http.get(self.agent_card_url, headers=self.headers)
                resp.raise_for_status()
                card_data = resp.json()
        except Exception as e:
            error_msg = f"A2A Agent Card 获取失败 [{self.agent_card_url}]: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        self._card = ParseDict(card_data, a2a_pb2.AgentCard(), ignore_unknown_fields=True)
        # 标准化 protocol_binding：Agent Card 常用 "json-rpc"，SDK 认 "JSONRPC"
        for iface in self._card.supported_interfaces:
            raw = iface.protocol_binding.lower().replace("-", "").replace("_", "")
            if raw in ("jsonrpc",):
                iface.protocol_binding = "JSONRPC"
        logger.info(f"A2A Agent Card 获取成功: {self.agent_card_url}")
        return self._card

    async def send(self, user_input: str, session_id: str = "",
                   context: Dict[str, Any] = None) -> str:
        """发送消息到对端 Agent 并返回完整响应文本

        Args:
            user_input: 用户输入文本
            session_id: 会话ID
            context: 额外上下文（暂未使用，保留接口兼容性）

        Returns:
            对端 Agent 返回的完整响应文本
        """
        card = await self._fetch_agent_card()

        client = await create_client(
            agent=card,
            client_config=ClientConfig(
                httpx_client=httpx.AsyncClient(
                    headers=self.headers,
                    timeout=self.timeout,
                ),
            ),
        )

        try:
            async with client:
                output_parts: list[str] = []
                request = a2a_pb2.SendMessageRequest(
                    message=a2a_pb2.Message(
                        role=a2a_pb2.Role.ROLE_USER,
                        parts=[a2a_pb2.Part(text=user_input)],
                    ),
                )

                async for resp in client.send_message(request):
                    if resp.HasField("task"):
                        for art in resp.task.artifacts:
                            for part in art.parts:
                                if part.text:
                                    output_parts.append(part.text)
                    elif resp.HasField("message"):
                        for part in resp.message.parts:
                            if part.text:
                                output_parts.append(part.text)

                result = "\n".join(output_parts)
                logger.info(f"A2A Agent 响应 [{self.agent_card_url}]: {len(result)} chars")
                return result if result else "A2A Agent 未返回文本响应"

        except Exception as e:
            error_msg = f"A2A Agent 调用失败 [{self.agent_card_url}]: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
