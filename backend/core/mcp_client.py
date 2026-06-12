import httpx
import time
from typing import List, Dict, Any, Optional
from loguru import logger


class McpServerConnection:
    def __init__(self, base_url: str, headers: Dict[str, str], single_endpoint: bool = False):
        self.base_url = base_url
        self.headers = headers
        self.single_endpoint = single_endpoint
        self.initialized = False
        self.tools: List[Dict] = []
        self.last_used_at = time.time()


class MCPClient:
    REQUEST_TIMEOUT = 30
    TOOL_CALL_TIMEOUT = 60

    def __init__(self):
        self._connections: Dict[int, McpServerConnection] = {}
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT)
        return self._client

    async def connect(self, server_id: int, base_url: str, headers: Dict[str, str] = None, single_endpoint: bool = False) -> McpServerConnection:
        base_url = base_url.rstrip("/")
        headers = headers or {}

        if server_id in self._connections:
            conn = self._connections[server_id]
            if await self.ping(conn):
                conn.last_used_at = time.time()
                return conn

        conn = McpServerConnection(base_url=base_url, headers=headers, single_endpoint=single_endpoint)
        client = await self._get_client()

        init_url = base_url if single_endpoint else f"{base_url}/initialize"
        resp = await client.post(
            init_url,
            json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "hh-agent-hub", "version": "1.0.0"},
                },
            },
            headers=headers,
        )
        resp.raise_for_status()

        notif_url = base_url if single_endpoint else f"{base_url}/notifications/initialized"
        await client.post(
            notif_url,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=headers,
        )
        conn.initialized = True
        self._connections[server_id] = conn
        logger.info(f"MCP [{base_url}] connected (single_endpoint={single_endpoint})")
        return conn

    async def ping(self, conn: McpServerConnection) -> bool:
        try:
            client = await self._get_client()
            url = conn.base_url if conn.single_endpoint else f"{conn.base_url}/ping"
            resp = await client.post(
                url,
                json={"jsonrpc": "2.0", "id": 0, "method": "ping"},
                headers=conn.headers, timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def discover_tools(self, server_id: int) -> List[Dict]:
        conn = self._connections.get(server_id)
        if not conn:
            raise ValueError(f"MCP Server {server_id} not connected")
        client = await self._get_client()
        url = conn.base_url if conn.single_endpoint else f"{conn.base_url}/tools/list"
        resp = await client.post(
            url,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=conn.headers,
        )
        resp.raise_for_status()
        data = resp.json()
        tools = data.get("result", {}).get("tools", [])
        conn.tools = [{
            "name": t["name"],
            "description": t.get("description", ""),
            "inputSchema": t.get("inputSchema", {"type": "object", "properties": {}}),
        } for t in tools]
        logger.info(f"Discovered {len(conn.tools)} tools from {conn.base_url}")
        return conn.tools

    async def call_tool(self, server_id: int, tool_name: str, arguments: Dict[str, Any]) -> str:
        conn = self._connections.get(server_id)
        if not conn:
            raise ValueError(f"MCP Server {server_id} not connected")
        conn.last_used_at = time.time()
        client = await self._get_client()
        url = conn.base_url if conn.single_endpoint else f"{conn.base_url}/tools/call"
        payload = {
            "jsonrpc": "2.0", "id": int(time.time() * 1000), "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        try:
            resp = await client.post(
                url, json=payload, headers=conn.headers, timeout=self.TOOL_CALL_TIMEOUT,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"[MCP] tools/call HTTP {e.response.status_code}: {e.response.text[:500]}")
            raise
        except httpx.TimeoutException:
            logger.error(f"[MCP] tools/call timeout after {self.TOOL_CALL_TIMEOUT}s")
            raise
        data = resp.json()
        if "error" in data:
            err = data["error"]
            logger.error(f"[MCP] tools/call JSON-RPC error: code={err.get('code')}, message={err.get('message')}")
            raise Exception(f"MCP Error [{err.get('code')}]: {err.get('message')}")
        result = data.get("result")
        if result is None:
            logger.warning(f"[MCP] tools/call returned null result: {resp.text[:500]}")
            return ""
        if not isinstance(result, dict):
            logger.error(f"[MCP] tools/call unexpected result type={type(result).__name__}, raw: {resp.text[:500]}")
            return ""
        content_parts = []
        for item in (result.get("content") or []):
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                content_parts.append(item.get("text", ""))
            elif item.get("type") == "resource":
                content_parts.append(item.get("text", "") or item.get("uri", ""))
        return "\n".join(content_parts)

    def disconnect(self, server_id: int):
        self._connections.pop(server_id, None)

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connections.clear()


mcp_client = MCPClient()
