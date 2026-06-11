## 文档版本
| 版本 | 日期 | 作者 | 说明 |

---

## 四、API设计

### 4.1 API规范

- **基础路径**：`/api/v1`
- **认证方式**：Header `X-API-Key` 或 `Authorization: Bearer <token>`
- **响应格式**：JSON
- **错误码**：标准HTTP状态码

### 4.2 系统配置API

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /configs | 获取所有配置 | admin |
| GET | /configs/{key} | 获取单个配置 | admin |
| PUT | /configs/{key} | 更新配置 | admin |
| POST | /configs/test-llm | 测试LLM连接 | admin |

### 4.3 Agent管理API

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /agents | 获取Agent列表 | user |
| GET | /agents/{id} | 获取Agent详情 | user |
| POST | /agents | 创建Agent | user |
| PUT | /agents/{id} | 更新Agent | user |
| DELETE | /agents/{id} | 删除Agent | user |
| POST | /agents/{id}/test | 测试Agent对话 | user |
| POST | /agents/{id}/copy | 复制Agent | user |

**请求/响应示例**：

```json
// POST /agents
{
  "name": "data_query_agent",
  "display_name": "数据查询专家",
  "description": "负责查询数据库表大小、慢查询日志、服务状态",
  "role": "worker",
  "llm_config": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0.1
  },
  "system_prompt": "你是数据查询专家，只回答数据类问题...",
  "mcp_servers": [...]
}

// 响应
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "name": "data_query_agent",
    "created_at": "2026-01-15T10:00:00Z"
  }
}
```

### 4.4 工作流管理API

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /workflows | 获取工作流列表 | user |
| GET | /workflows/{id} | 获取工作流详情 | user |
| POST | /workflows | 创建工作流 | user |
| PUT | /workflows/{id} | 更新工作流 | user |
| DELETE | /workflows/{id} | 删除工作流 | user |
| POST | /workflows/{id}/publish | 发布工作流 | user |
| GET | /workflows/{id}/graph | 获取图结构 | user |
| POST | /workflows/{id}/validate | 验证工作流 | user |

### 4.5 应用管理API

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /apps | 获取应用列表 | user |
| GET | /apps/{id} | 获取应用详情 | user |
| POST | /apps | 创建应用 | user |
| PUT | /apps/{id} | 更新应用 | user |
| DELETE | /apps/{id} | 删除应用 | user |
| POST | /apps/{id}/rotate-key | 轮换API密钥 | user |
| GET | /apps/{id}/stats | 获取调用统计 | user |

### 4.6 对话API（对外核心）

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | /chat | 对话接口 | API Key |
| GET | /chat/sessions/{session_id} | 获取会话历史 | API Key |
| DELETE | /chat/sessions/{session_id} | 清除会话 | API Key |

**请求体**：
```json
{
  "app_id": 1,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "查询最近一小时的慢查询",
  "stream": false
}
```

**非流式响应**：
```json
{
  "code": 0,
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "根据查询结果，最近一小时有3条慢查询...",
    "intermediate_results": {
      "data_query_agent": "找到3条慢查询，最慢的是SELECT * FROM orders WHERE...",
      "analyzer": "建议为orders表的create_time字段添加索引"
    },
    "usage": {
      "input_tokens": 1500,
      "output_tokens": 800
    },
    "duration_ms": 2340
  }
}
```

**流式响应（SSE）**：
```
event: thinking
data: {"content": "正在分析问题..."}

event: agent_call
data: {"agent": "data_query_agent", "input": "查询最近一小时慢查询"}

event: agent_result
data: {"agent": "data_query_agent", "output": "找到3条慢查询"}

event: text
data: {"content": "根据查询结果"}

event: text
data: {"content": "，最近一小时有3条慢查询："}

event: text
data: {"content": "\n1. SELECT * FROM orders... 耗时2.3s"}

event: done
data: {"session_id": "550e8400-e29b-41d4-a716-446655440000"}
```

### 4.7 MCP Server 资源目录 API

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /mcp-servers | 获取 MCP Server 列表 | user |
| GET | /mcp-servers/{id} | 获取详情（含 discovered_tools） | user |
| POST | /mcp-servers | 注册新的 MCP Server | admin |
| PUT | /mcp-servers/{id} | 更新 MCP Server 配置 | admin |
| DELETE | /mcp-servers/{id} | 删除 MCP Server | admin |
| POST | /mcp-servers/{id}/discover | 触发工具发现（tools/list） | admin |
| POST | /mcp-servers/{id}/test | 测试连接（调用 ping） | admin |

```json
// POST /mcp-servers
{
  "name": "mysql-prod",
  "display_name": "生产环境 MySQL",
  "description": "查询生产数据库表大小、慢查询日志等",
  "command": "npx",
  "args": ["-y", "@anthropic/mcp-server-mysql"],
  "env_vars": {
    "MYSQL_HOST": "prod-db.internal",
    "MYSQL_PASSWORD": "${MYSQL_PROD_PASSWORD}"
  }
}

// Response
{
  "code": 0,
  "data": {
    "id": 1,
    "name": "mysql-prod",
    "discovered_tools": [
      {"name": "query_slow_log", "description": "查询慢查询日志"},
      {"name": "query_table_size", "description": "查询表大小"},
      {"name": "execute_sql", "description": "执行SQL语句"}
    ]
  }
}
```

**Agent 选用 MCP Server API**（在创建/更新 Agent 时使用）：

```json
// POST /agents - 请求中指定关联的 MCP Server
{
  "name": "data_query_agent",
  "agent_type": "local",
  "mcp_links": [
    {
      "mcp_server_id": 1,
      "enabled_tools": ["query_slow_log", "query_table_size"]
    }
  ]
}
```

### 4.8 知识库管理 API

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /knowledge-bases | 获取知识库列表 | user |
| GET | /knowledge-bases/{id} | 获取详情 | user |
| POST | /knowledge-bases | 创建知识库 | admin |
| PUT | /knowledge-bases/{id} | 更新知识库 | admin |
| DELETE | /knowledge-bases/{id} | 删除知识库 | admin |
| POST | /knowledge-bases/{id}/sync | 同步/重建文档索引 | admin |
| GET | /knowledge-bases/{id}/documents | 获取文档列表 | user |
| POST | /knowledge-bases/{id}/documents | 上传文档 | admin |
| DELETE | /knowledge-bases/{id}/documents/{doc_id} | 删除文档 | admin |

```json
// POST /knowledge-bases
{
  "name": "api-docs",
  "display_name": "API 文档库",
  "description": "公司内部 API 文档",
  "kb_type": "file",
  "config": {
    "source_path": "/data/knowledge/api_docs/",
    "file_patterns": ["*.md", "*.yaml", "*.json"]
  }
}

// Agent 选用知识库 - 在创建/更新 Agent 时指定
{
  "name": "api_developer",
  "agent_type": "claudecode",
  "kb_ids": [1, 2]
}
```

### 4.9 Skill 资源目录 API

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /skills | 获取 Skill 列表（支持分类/标签过滤） | user |
| GET | /skills/{id} | 获取详情 | user |
| POST | /skills | 创建 Skill 模板 | admin |
| PUT | /skills/{id} | 更新 Skill | admin |
| DELETE | /skills/{id} | 删除 Skill | admin |

```json
// POST /skills
{
  "name": "slow-query-analysis",
  "display_name": "慢查询分析",
  "description": "数据库慢查询分析标准流程",
  "skill_type": "prompt",
  "content": {
    "prompt_template": "## 慢查询分析\n1. 使用 query_slow_log 工具获取慢查询\n2. 对每条慢查询获取 EXPLAIN 结果\n3. 分析索引使用情况\n4. 给出优化建议"
  },
  "category": "ops",
  "tags": ["mysql", "performance"]
}

// Agent 选用 Skill - 在创建/更新 Agent 时指定
{
  "name": "dba_agent",
  "agent_type": "local",
  "skill_ids": [1, 2, 5]
}
```

### 4.10 统一资源查询 API

```json
// GET /api/v1/resources?type=all  — 一次性获取所有可用资源
{
  "code": 0,
  "data": {
    "mcp_servers": [...],
    "knowledge_bases": [...],
    "skills": [...]
  }
}
```


