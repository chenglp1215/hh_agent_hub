## 文档版本
| 版本 | 日期 | 作者 | 说明 |
| v3.0 | 2026-06-24 | - | 更新容器化 Agent 执行架构，新增 reasonix 类型 |

# Agent 体系设计

### 5.3 Agent节点工厂

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

class AgentNodeFactory:
    """根据配置创建Agent节点"""

    async def create(self, agent_config: dict):
        agent_type = agent_config.get("agent_type", "local")
        if agent_type == "local":
            return await self.create_local_agent(agent_config)
        elif agent_type == "http":
            return await self.create_http_agent(agent_config)
        elif agent_type == "a2a":
            return await self.create_a2a_agent(agent_config)
        elif agent_type == "claudecode":
            return await self.create_claudecode_agent(agent_config)
        elif agent_type == "reasonix":
            return await self.create_reasonix_agent(agent_config)
```


---

### 5.5 知识库检索与注入

#### 5.5.1 v1 策略：直接注入，不上向量库

知识库规模较小（几十个 Markdown 文档），v1 采用**按标题分块 + 关键词匹配 + 直接注入 Prompt**，不引入向量数据库。

```
knowledge_bases (kb_type=file)
    │
    ▼
目录扫描: 遍历 source_path 下所有匹配 file_patterns 的文件
    │
    ▼
Markdown 分块: 按 ## 标题拆分段落，保留标题层级路径
    │
    ▼
存储: content_blocks 表，每个块 = (kb_id, source_file, heading_path, body, token_count)
    │
    ▼
检索: 用户问题 → 关键词提取 → SQL LIKE 匹配标题+正文
    │
    ▼
排序: 匹配数 + 标题层级相似度
    │
    ▼
注入: Top-K chunk 拼入 Agent System Prompt 的 "## 参考资料" 区块
```

#### 5.5.6 典型注入示例

用户问"数据库慢查询怎么排查"，Agent 自动获得注入了知识库内容：

```markdown
## 你的角色
你是运维专家...

## 参考资料（来自知识库）
### 数据库运维 > MySQL > 慢查询分析
1. 使用 query_slow_log 工具获取近 1 小时的慢查询列表
2. 对耗时最长的 3 条执行 EXPLAIN 分析
...
```


---

### 5.6 HTTP Agent 设计

HTTP Agent 通过 HTTP 接口对接外部的 Agent Chat 服务。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| base_url | string | 是 | 外部服务基础URL |
| endpoint | string | 否 | 聊天接口路径，默认 `/chat` |
| headers | object | 否 | 请求头，用于认证等 |
| timeout | int | 否 | 超时时间(秒)，默认30 |


---

### 5.7 A2A Agent 设计

A2A Agent 通过 A2A 协议（JSON-RPC）与对端 Agent 通信。

```json
{
  "agent_type": "a2a",
  "a2a_config": {
    "agent_card_url": "http://peer-agent:8080/.well-known/agent-card.json",
    "headers": {"X-API-Key": "sk-xxx"},
    "timeout": 30
  }
}
```

流程：
1. 获取 Agent Card（`/.well-known/agent-card.json`）
2. 通过 A2A SDK 创建客户端
3. 发送 `SendMessageRequest`（含 `message_id`、`role`、`parts`）
4. 解析流式响应，提取文本结果


---

### 5.9 容器化 Agent 类型（Claude Code / Reasonix）

#### 5.9.1 概述

平台支持 5 种 Agent 类型：

| 类型 | 核心引擎 | 执行方式 | 适用场景 |
|------|---------|---------|---------|
| **local** | LangChain ReAct Agent | Worker 进程内 | 通用对话、工具调用 |
| **http** | HTTP Client | Worker 进程内 | 对接外部 Agent API |
| **a2a** | A2A SDK (JSON-RPC) | Worker 进程内 | Agent 间通信 |
| **claudecode** | Claude Code CLI | **独立 Docker 容器** | 代码分析、文件操作、项目级任务 |
| **reasonix** | Reasonix CLI (DeepSeek) | **独立 Docker 容器** | 代码分析（低成本，只读） |

claudecode 和 reasonix 类型采用容器化执行：Worker 通过 Docker SDK 在宿主机上启动临时容器（`--rm`），容器内运行 CLI 工具，执行完毕后自动销毁。

```
┌─ Worker 容器 ──────────────────────────────────────────────────┐
│                                                                 │
│  AgentNodeFactory.create("claudecode")                          │
│       │                                                         │
│       ▼                                                         │
│  DockerClaudeCodeRunner                                         │
│       │                                                         │
│       ├─ 1. Git clone 项目代码                                  │
│       ├─ 2. 写入 CLAUDE.md + .claude/settings.json              │
│       ├─ 3. 路径转换 (容器内路径 → 宿主机路径)                  │
│       ├─ 4. docker run --rm 启动临时容器                        │
│       └─ 5. 捕获 stdout JSON 结果                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼ (通过 /var/run/docker.sock)
┌─ Claude Code 临时容器 (hh-claudecode:latest) ──────────────────┐
│  /workspace/                    ← 挂载的项目代码目录            │
│    .git/                        ← Git 仓库                     │
│    CLAUDE.md                    ← 系统指令                     │
│    .claude/settings.json        ← API 配置 + 权限              │
│                                                                 │
│  claude --print --output-format json --model xxx -p -           │
│  (从 stdin 读取 user_input，多轮工具调用，输出 JSON 结果)       │
│                                                                 │
│  执行完毕 → 容器自动销毁 (--rm)                                │
└─────────────────────────────────────────────────────────────────┘
```

#### 5.9.2 Agent 类型枚举

```
agent_type: 'local' | 'http' | 'a2a' | 'claudecode' | 'reasonix'
```

#### 5.9.3 Claude Code Agent 配置

```json
{
  "agent_type": "claudecode",
  "claudecode_config": {
    "project_registry_id": 1,
    "settings_registry_id": 2
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| project_registry_id | int | 关联 ProjectRegistry（Git 仓库、分支、认证） |
| settings_registry_id | int | 关联 ClaudeSettingsRegistry（settings_json、model、权限） |

**settings_json** 直接原样写入容器的 `.claude/settings.json`，不做解析。

#### 5.9.4 Reasonix Agent 配置

```json
{
  "agent_type": "reasonix",
  "reasonix_config": {
    "project_registry_id": 1,
    "deepseek_api_key": "sk-xxx",
    "deepseek_model": "deepseek-chat",
    "max_turns": 25
  }
}
```

> **注意**：Reasonix 的 `run` 模式为只读，不执行文件写入操作。适合代码分析、Review、报告生成等场景。

#### 5.9.5 容器化执行流程

```
Worker 进程内:
  ① 解析配置 (registry → DB 查询)
  ② Git clone/pull 项目代码
  ③ 写入 CLAUDE.md (system prompt + skills + KB + 上游结果)
  ④ 写入 .claude/settings.json (原样 settings_json)
  ⑤ 路径转换: /data/workflow_workspaces/... → /opt/hh_agent_hub/workspaces/...
  ⑥ echo -n "{user_input}" | docker run --rm -i -v {host_path}:/workspace ...
  ⑦ 等待容器执行完毕，捕获 stdout JSON
  ⑧ 解析返回结果
```

**路径转换**：Worker 容器内路径与宿主机路径不同（bind mount）。通过 `WORKSPACE_HOST_PATH` 环境变量配置映射。

#### 5.9.6 容器镜像

| 镜像 | 基础 | 大小 | 安装 |
|------|------|------|------|
| hh-claudecode | node:22-alpine | ~260MB | @anthropic-ai/claude-code |
| hh-reasonix | node:22-alpine | ~260MB | reasonix |

#### 5.9.7 资源限制

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--memory` | 512m | 容器内存上限 |
| `--cpus` | 1.0 | CPU 限制 |
| `--network` | hh_agent_hub_agent-net | Docker 网络 |
| `--user` | 1001:1001 | 容器内用户 |
| timeout | project.fix_timeout_minutes * 60 | 超时 |

#### 5.9.8 工作流混用示例

```
工作流：代码审查 + 测试 + 部署
├── 主管Agent（local）
│   └── LLM: 路由决策
│
├── 代码分析Agent（claudecode）
│   ├── 项目: mdr_theseus
│   └── 执行: Docker 容器内 claude CLI
│
├── 自动化测试Agent（a2a）
│   └── URL: http://autotest-agent:8002
│
└── 部署Agent（http）
    └── URL: http://deploy-system:8080/deploy
```
