import re
from typing import Dict, Any, Optional
import httpx
from loguru import logger


class HttpAgentClient:
    """HTTP Agent 客户端 — 通过 HTTP 调用外部 Agent Chat 服务"""

    def __init__(self, http_config: Dict[str, Any]):
        self.base_url = http_config.get("base_url", "").rstrip("/")
        self.endpoint = http_config.get("endpoint", "/chat")
        self.method = http_config.get("method", "POST").upper()
        self.headers = http_config.get("headers", {})
        self.timeout = http_config.get("timeout", 30)
        self.retry_config = http_config.get("retry", {"max_attempts": 3, "delay_ms": 1000})
        self.request_template = http_config.get("request_template", {})
        self.response_mapping = http_config.get("response_mapping", {})

    async def send(self, user_input: str, session_id: str = "",
                   context: Dict[str, Any] = None) -> str:
        """发送请求到外部 Agent 服务并返回响应文本"""
        url = f"{self.base_url}{self.endpoint}"
        body = self._build_request_body(user_input, session_id, context)
        headers = self._build_headers()

        max_attempts = self.retry_config.get("max_attempts", 3)
        delay_ms = self.retry_config.get("delay_ms", 1000)

        last_error = None
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if self.method == "POST":
                        resp = await client.post(url, json=body, headers=headers)
                    elif self.method == "GET":
                        resp = await client.get(url, params=body, headers=headers)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {self.method}")

                    resp.raise_for_status()
                    data = resp.json()

                    # Extract output using response_mapping
                    output = self._extract_output(data)
                    logger.info(f"HTTP Agent response from {url}: {len(output)} chars")
                    return output

            except Exception as e:
                last_error = e
                logger.warning(f"HTTP Agent attempt {attempt + 1}/{max_attempts} failed: {e}")
                if attempt < max_attempts - 1:
                    import asyncio
                    await asyncio.sleep(delay_ms / 1000)

        raise RuntimeError(f"HTTP Agent failed after {max_attempts} attempts: {last_error}")

    def _build_request_body(self, user_input: str, session_id: str,
                            context: Dict[str, Any] = None) -> Dict[str, Any]:
        """根据 request_template 构建请求体"""
        if not self.request_template:
            return {"message": user_input, "session_id": session_id}

        body = {}
        context_json = str(context) if context else ""
        for key, value in self.request_template.items():
            if isinstance(value, str):
                value = value.replace("{{user_input}}", user_input)
                value = value.replace("{{session_id}}", session_id)
                value = value.replace("{{context}}", context_json)
            body[key] = value
        return body

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头（替换环境变量占位符）"""
        headers = {}
        for key, value in self.headers.items():
            if isinstance(value, str):
                # 替换 ${VAR} 占位符
                import os
                def replacer(match):
                    var_name = match.group(1)
                    return os.getenv(var_name, match.group(0))
                value = re.sub(r'\$\{(\w+)\}', replacer, value)
            headers[key] = value
        return headers

    def _extract_output(self, data: Dict[str, Any]) -> str:
        """根据 response_mapping 从响应中提取输出"""
        output_field = self.response_mapping.get("output_field", "response")
        error_field = self.response_mapping.get("error_field", "")

        # Check for error first
        if error_field:
            error_val = self._get_nested(data, error_field)
            if error_val:
                raise RuntimeError(f"External agent error: {error_val}")

        # Extract output
        output = self._get_nested(data, output_field)
        if output is None:
            return str(data)
        return str(output)

    @staticmethod
    def _get_nested(data: Dict[str, Any], path: str) -> Any:
        """通过点号分隔的路径获取嵌套字段值，如 'response.content'"""
        if not path:
            return None
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
            if current is None:
                return None
        return current
