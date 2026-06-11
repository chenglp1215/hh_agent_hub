# MCP HTTP 客户端设计

## 一、设计决策

本系统**不启动也不管理** MCP Server 进程。MCP Server 由各团队独立运维（DBA 维护 MySQL MCP Server、运维维护 K8s MCP Server），平台仅作为 HTTP 客户端对接调用。

| 方案 | 本系统选择 | 被否决的方案 |
|------|:---:|:---:|
| 传输模式 | **Streamable HTTP** (HTTP POST + JSON) | stdio (子进程模式) |
| MCP Server 在哪 | 各团队独立部署的服务 | 平台 Worker 内子进程 |
| 平台做什么 | HTTP Client 调用 | 启动/管理/回收子进程 |
| 配置内容 | `base_url` + `headers` + `timeout` | `command` + `args` + `env` |

## 二、协议交互

MCP Streamable HTTP 协议基于标准 HTTP POST + JSON。

```
平台 (HTTP Client)                    MCP Server (外部 HTTP 服务)
    │                                       │
    │── POST {base_url}/initialize ────────▶│  ① 握手: 交换协议版本和能力
    │◀─ {jsonrpc:"2.0", result:{protocolVersion,...}}
    │                                       │
    │── POST {base_url}/tools/list ────────▶│  ② 发现工具列表
    │◀─ {tools: [{name, description, inputSchema}]}
    │                                       │
    │── POST {base_url}/tools/call ────────▶│  ③ 调用工具
    │◀─ {content: [{type: "text", text: "..."}]}
    │                                       │
    │── POST {base_url}/ping ──────────────▶│  ④ 健康检查
    │◀─ {}                                  │
```

## 三、HTTP 客户端实现

```python
# core/mcp_client.py
import httpx
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class McpServerConnection:
    """MCP Server 连接状态"""
    base_url: str
    headers: Dict[str, str]
    initialized: bool = False
    tools: List[Dict] = field(default_factory=list)
    last_used_at: float = field(default_factory=time.time)


class MCPClient:
    """MCP Streamable HTTP 客户端 — 不管理进程，纯 HTTP 调用"""

    REQUEST_TIMEOUT = 30
    TOOL_CALL_TIMEOUT = 60

    def __init__(self):
        self._connections: Dict[int, McpServerConnection] = {}
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT)
        return self._client

    # ========== 连接与握手 ==========

    async def connect(self, server_id: int, base_url: str,
                      headers: Dict[str, str] = None) -> McpServerConnection:
        """建立连接, 发送 initialize 握手"""
        base_url = base_url.rstrip("/")

        if server_id in self._connections:
            conn = self._connections[server_id]
            if await self.ping(conn):
                conn.last_used_at = time.time()
                return conn

        conn = McpServerConnection(base_url=base_url, headers=headers or {})
        client = await self._get_client()

        # initialize
        resp = await client.post(
            f"{base_url}/initialize",
            json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "hh-agent-hub", "version": "1.0.0"}
                }
            },
            headers=headers
        )
        resp.raise_for_status()
        data = resp.json()

        # initialized 通知
        await client.post(
            f"{base_url}/notifications/initialized",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=headers
        )

        conn.initialized = True
        self._connections[server_id] = conn
        logger.info(f"MCP [{base_url}] 连接成功, 协议: {data.get('result', {}).get('protocolVersion')}")
        return conn

    async def ping(self, conn: McpServerConnection) -> bool:
        """健康检查"""
        try:
            client = await self._get_client()
            resp = await client.post(
                f"{conn.base_url}/ping",
                json={"jsonrpc": "2.0", "id": 0, "method": "ping"},
                headers=conn.headers, timeout=5
            )
            return resp.status_code == 200
        except Exception:
            return False

    # ========== 工具发现 ==========

    async def discover_tools(self, server_id: int) -> List[Dict]:
        """发送 tools/list 获取工具清单"""
        conn = self._connections.get(server_id)
        if not conn:
            raise ValueError(f"MCP Server {server_id} 未连接")

        client = await self._get_client()
        resp = await client.post(
            f"{conn.base_url}/tools/list",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=conn.headers
        )
        resp.raise_for_status()
        data = resp.json()

        tools = data.get("result", {}).get("tools", [])
        conn.tools = [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "inputSchema": t.get("inputSchema", {"type": "object", "properties": {}})
            }
            for t in tools
        ]
        logger.info(f"发现 {len(conn.tools)} 个工具 from {conn.base_url}")
        return conn.tools

    # ========== 工具调用 ==========

    async def call_tool(self, server_id: int, tool_name: str,
                        arguments: Dict[str, Any]) -> str:
        """调用 MCP 工具"""
        conn = self._connections.get(server_id)
        if not conn:
            raise ValueError(f"MCP Server {server_id} 未连接")

        conn.last_used_at = time.time()
        client = await self._get_client()

        resp = await client.post(
            f"{conn.base_url}/tools/call",
            json={
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments}
            },
            headers=conn.headers,
            timeout=self.TOOL_CALL_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            err = data["error"]
            raise Exception(f"MCP Error [{err.get('code')}]: {err.get('message')}")

        # 解析 content
        content_parts = []
        for item in data.get("result", {}).get("content", []):
            if item.get("type") == "text":
                content_parts.append(item["text"])
            elif item.get("type") == "resource":
                content_parts.append(item.get("text", "") or item.get("uri", ""))
        return "\n".join(content_parts)

    # ========== LangChain 工具适配 ==========

    async def load_tools(self, server_id: int, base_url: str,
                         headers: Dict, enabled_tools: List[str] = None) -> List:
        """将 MCP 工具转换为 LangChain Tool"""
        from langchain_core.tools import tool

        conn = await self.connect(server_id, base_url, headers)
        tools_meta = await self.discover_tools(server_id)

        langchain_tools = []
        sid = server_id

        for meta in tools_meta:
            tool_name = meta["name"]

            # 工具级过滤
            if enabled_tools and tool_name not in enabled_tools:
                continue

            @tool
            async def wrapped_tool(**kwargs) -> str:
                return await self.call_tool(sid, tool_name, kwargs)

            wrapped_tool.name = tool_name
            wrapped_tool.description = meta.get("description", "")
            langchain_tools.append(wrapped_tool)

        return langchain_tools

    def disconnect(self, server_id: int):
        self._connections.pop(server_id, None)

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connections.clear()


# 全局单例
mcp_client = MCPClient()
```

## 四、MCP Server 注册表

### 4.1 表结构

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | |
| name | VARCHAR(100) UNIQUE | 标识名, 如 `mysql-prod` |
| display_name | VARCHAR(100) | 显示名称 |
| description | TEXT | 功能描述 |
| **base_url** | VARCHAR(500) | MCP Server 地址, 如 `http://mysql-mcp.internal:3000` |
| **headers** | JSON | 请求头, 如 `{"Authorization": "Bearer xxx"}` |
| **timeout** | INT DEFAULT 30 | 请求超时(秒) |
| discovered_tools | JSON | 自动发现的工具列表 |
| status | VARCHAR(20) | active / disabled / error |
| last_checked_at | DATETIME | 上次连接检查时间 |
| created_by | FK→users | |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### 4.2 注册示例

```json
{
  "name": "mysql-prod",
  "display_name": "生产环境 MySQL MCP",
  "base_url": "http://mysql-mcp.dba-team.internal:3000",
  "headers": {
    "Authorization": "Bearer mcp-token-abc123"
  },
  "timeout": 30
}
```

### 4.3 MCP Server 管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /mcp-servers | 列表 |
| POST | /mcp-servers | 注册 (base_url + headers + timeout) |
| PUT | /mcp-servers/{id} | 更新 |
| DELETE | /mcp-servers/{id} | 删除 |
| POST | /mcp-servers/{id}/discover | 触发 tools/list |
| POST | /mcp-servers/{id}/test | 测试连接 (ping) |

## 五、部署影响

| 影响 | 说明 |
|------|------|
| Worker 不再需要 Node.js | Dockerfile 去掉 `nodejs npm` |
| Worker 不需要 Docker socket | docker-compose 去掉 `/var/run/docker.sock` |
| MCP 子进程相关代码删除 | ~300 行进程管理代码不再需要 |
| MCP 心跳/超时回收逻辑删除 | 不需要检查进程存活, 只需 HTTP ping |
