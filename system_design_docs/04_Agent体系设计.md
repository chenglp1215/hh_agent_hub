## 文档版本
| 版本 | 日期 | 作者 | 说明 |

# Agent 体系设计

### 5.3 Agent节点工厂

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

class AgentNodeFactory:
    """根据配置创建Agent节点"""
    
    def __init__(self, mcp_client: MCPClient):
        self.mcp_client = mcp_client
    
    def create(self, agent_config: dict):
        """创建单个Agent的执行函数"""
        # 1. 初始化LLM
        llm = self._init_llm(agent_config["llm_config"])
        
        # 2. 加载MCP工具
        tools = []
        for mcp_server in agent_config.get("mcp_servers", []):
            tools.extend(self.mcp_client.load_tools(mcp_server))
        
        # 3. 加载Skills（作为Prompt上下文）
        skills_context = self._load_skills(agent_config.get("skills", []))
        full_prompt = agent_config["system_prompt"] + "\n\n" + skills_context
        
        # 4. 创建ReAct Agent
        react_agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=full_prompt
        )
        
        # 5. 返回节点函数
        def agent_node(state: AgentState) -> dict:
            result = react_agent.invoke({
                "messages": state.get("messages", []),
                "user_input": state["user_input"]
            })
            return {
                "messages": result["messages"],
                "intermediate_results": {
                    **state.get("intermediate_results", {}),
                    agent_config["name"]: result["output"]
                }
            }
        
        return agent_node
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

#### 5.5.2 检索器抽象

```python
from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass

@dataclass
class SearchResult:
    """检索结果"""
    chunk_id: int
    heading_path: str       # 如 "API 文档 > 用户模块 > 登录接口"
    content: str
    source_file: str
    score: float            # 0.0~1.0

class KnowledgeRetriever(ABC):
    """知识库检索器抽象基类 — v1 关键词版，后续可替换为 Chroma"""

    @abstractmethod
    async def search(self, kb_ids: List[int], query: str, top_k: int = 5) -> List[SearchResult]:
        ...


class KeywordRetriever(KnowledgeRetriever):
    """v1 关键词检索器"""

    async def search(self, kb_ids: List[int], query: str, top_k: int = 5) -> List[SearchResult]:
        # 1. 提取关键词
        keywords = self._extract_keywords(query)

        # 2. SQL 模糊匹配
        # SELECT * FROM content_blocks
        # WHERE kb_id IN (?) AND (heading_path LIKE '%keyword%' OR body LIKE '%keyword%')

        # 3. 按匹配度排序（标题命中权重 > 正文命中权重）
        results = sorted(results, key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def _extract_keywords(self, query: str) -> List[str]:
        # 简单分词 + 去停用词
        pass
```

#### 5.5.3 Agent 运行时注入

Agent Factory 在创建节点时，根据 Agent 关联的知识库自动检索并注入上下文：

```python
class KnowledgeInjector:
    """知识库上下文注入器"""

    def __init__(self, retriever: KnowledgeRetriever):
        self.retriever = retriever

    async def inject(self, kb_ids: List[int], user_query: str,
                     base_prompt: str, max_tokens: int = 2000) -> str:
        """将知识库内容注入 Agent Prompt"""
        if not kb_ids:
            return base_prompt

        # 1. 检索相关 chunk
        results = await self.retriever.search(kb_ids, user_query, top_k=5)

        # 2. 控制 token 总量
        injected_content = []
        token_count = 0
        for r in results:
            estimated_tokens = len(r.content) // 2  # 粗略估算
            if token_count + estimated_tokens > max_tokens:
                break
            injected_content.append(f"### {r.heading_path}\n{r.content}")
            token_count += estimated_tokens

        # 3. 拼接
        if injected_content:
            base_prompt += "\n\n## 参考资料（来自知识库）\n" + "\n\n".join(injected_content)

        return base_prompt


# 全局单例
knowledge_injector = KnowledgeInjector(KeywordRetriever())
```

#### 5.5.4 content_blocks 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| kb_id | INTEGER | NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE | |
| source_file | VARCHAR(500) | NOT NULL | 源文件路径 |
| heading_path | VARCHAR(500) | | 标题层级路径 |
| body | TEXT | NOT NULL | chunk 正文内容 |
| token_count | INTEGER | DEFAULT 0 | 估算 token 数 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | |

索引：
```sql
CREATE INDEX idx_content_blocks_kb_id ON content_blocks(kb_id);
CREATE INDEX idx_content_blocks_heading ON content_blocks(heading_path);
```

#### 5.5.5 同步机制

知识库在以下时机触发重新分块和索引：

| 触发时机 | 方式 |
|---------|------|
| 知识库创建 | 自动同步 |
| 上传新文档 | POST `/knowledge-bases/{id}/documents` 后自动同步 |
| 手动触发 | POST `/knowledge-bases/{id}/sync` |
| 定时任务 | 每天凌晨 3 点全量同步（可选） |

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

### 数据库运维 > MySQL > 常见性能问题
索引缺失是最常见的性能问题，表现为...
```


---

### 5.6 HTTP Agent 设计

#### 5.6.1 概述（原 5.5）

#### 5.5.1 概述

HTTP Agent 是一种特殊的 Agent 类型，通过 HTTP 接口对接外部的 Agent Chat 服务。这种设计允许平台集成：

1. **第三方 AI 服务**：如其他 Agent 平台、外部 AI API
2. **企业内部服务**：已有的 Agent 服务、遗留系统
3. **多语言实现的 Agent**：用 Python 以外的语言实现的 Agent

#### 5.5.2 架构对比

```
┌─────────────────────────────────────────────────────────────────┐
│                      Local Agent（local类型）                    │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐          │
│  │  LLM配置    │   │  MCP工具    │   │  Skills     │          │
│  │ (OpenAI/    │   │  (MySQL/    │   │  (知识库)   │          │
│  │  Anthropic) │   │   K8s)      │   │             │          │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘          │
│         │                 │                 │                  │
│         └─────────────────┼─────────────────┘                  │
│                           ▼                                    │
│              ┌─────────────────────────┐                       │
│              │   LangGraph Runtime     │                       │
│              │   (本地执行)            │                       │
│              └─────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      HTTP Agent（http类型）                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                     HTTP配置                             │   │
│  │  base_url: http://external-agent:8080                   │   │
│  │  endpoint: /chat                                        │   │
│  │  headers: { Authorization: Bearer xxx }                 │   │
│  └────────────────────────┬────────────────────────────────┘   │
│                           ▼                                    │
│              ┌─────────────────────────┐                       │
│              │   HTTP Client           │                       │
│              │   (远程调用)            │                       │
│              └───────────┬─────────────┘                       │
└──────────────────────────┼──────────────────────────────────────┘
                           │
                           ▼
        ┌─────────────────────────────────────────────┐
        │         外部 Agent Chat HTTP API            │
        │  ┌───────────────────────────────────────┐  │
        │  │  POST /chat                          │  │
        │  │  {                                   │  │
        │  │    "message": "查询慢查询日志",       │  │
        │  │    "session_id": "xxx"               │  │
        │  │  }                                   │  │
        │  └───────────────────────────────────────┘  │
        │                                             │
        │  ┌───────────────────────────────────────┐  │
        │  │  Response:                           │  │
        │  │  {                                   │  │
        │  │    "response": {                     │  │
        │  │      "content": "找到3条慢查询..."    │  │
        │  │    }                                 │  │
        │  │  }                                   │  │
        │  └───────────────────────────────────────┘  │
        └─────────────────────────────────────────────┘
```

#### 5.5.3 HTTP Agent 配置详解

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| base_url | string | 是 | 外部服务基础URL |
| endpoint | string | 否 | 聊天接口路径，默认 `/chat` |
| method | string | 否 | HTTP方法，默认 `POST` |
| headers | object | 否 | 请求头，用于认证等 |
| timeout | int | 否 | 超时时间(秒)，默认30 |
| retry | object | 否 | 重试配置 |
| request_template | object | 否 | 请求体模板 |
| response_mapping | object | 否 | 响应字段映射 |

**请求模板变量**：
- `{{user_input}}`: 用户输入内容
- `{{session_id}}`: 会话ID
- `{{context}}`: 上下文信息（JSON）

**响应映射**：
- 支持嵌套字段访问，如 `response.content`
- 自动提取外部Agent的输出内容

#### 5.5.4 典型使用场景

**场景1：对接企业内部Agent服务**
```json
{
  "name": "internal_ops_agent",
  "agent_type": "http",
  "http_config": {
    "base_url": "http://ops-agent.internal.company.com",
    "endpoint": "/api/v1/chat",
    "headers": {
      "X-API-Key": "${OPS_AGENT_API_KEY}"
    },
    "timeout": 60
  }
}
```

**场景2：对接第三方Agent平台**
```json
{
  "name": "external_ai_agent",
  "agent_type": "http",
  "http_config": {
    "base_url": "https://api.external-ai.com",
    "endpoint": "/agent/chat",
    "headers": {
      "Authorization": "Bearer sk-xxx"
    },
    "request_template": {
      "prompt": "{{user_input}}",
      "conversation_id": "{{session_id}}",
      "model": "advanced"
    },
    "response_mapping": {
      "output_field": "result.text"
    }
  }
}
```

#### 5.5.5 工作流中的混用

平台支持在同一工作流中混用 Local Agent 和 HTTP Agent：

```
工作流：研发助手
├── 主管Agent（local）
│   ├── LLM: GPT-4
│   └── 功能: 任务路由
│
├── 数据查询Agent（local）
│   ├── LLM: GPT-4o-mini
│   └── MCP: MySQL
│
├── 运维操作Agent（http）
│   └── URL: http://ops-agent:8080/chat
│
└── 工单处理Agent（http）
    └── URL: http://ticket-system:9090/agent
```

主管Agent根据任务类型，将请求路由到不同类型的Agent处理，最终汇总返回用户。



---

### 5.9 Claude Code Agent 类型

#### 5.9.1 概述

Claude Code Agent 是继 local、http 之后的第三种 Agent 类型，专门集成 Claude Code 的能力。与 local 类型的区别在于：

| 维度 | local Agent | claudecode Agent |
|------|-------------|------------------|
| 核心引擎 | LangChain ReAct Agent | Claude Code SDK（文件读写+命令执行） |
| 工具集 | MCP + 自定义工具 | Claude Code 原生工具（Read/Write/Edit/Bash/Grep/Glob） + MCP |
| 适用场景 | 通用对话、工具调用 | 代码分析、文件操作、项目级任务 |
| 工作目录 | 无 | 支持指定项目工作目录 |
| 权限模型 | 无 | 支持 permission_mode 配置 |

#### 5.9.2 配置 Schema

```json
{
  "agent_type": "claudecode",
  "claudecode_config": {
    "model": "claude-sonnet-4-6",
    "max_turns": 25,
    "work_dir": "/home/user/projects/",
    "permission_mode": "acceptEdits",
    "claude_md_path": "/data/claude_configs/agent_1.md",
    "extra_args": ["--verbose"],
    "allowed_tools": ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]
  }
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| model | string | 否 | `claude-sonnet-4-6` | Claude 模型版本 |
| max_turns | int | 否 | 25 | 最大对话轮次，防止死循环 |
| work_dir | string | 是 | - | Claude Code 的工作目录 |
| permission_mode | string | 否 | `default` | 权限模式：`default` / `acceptEdits` / `bypassPermissions` / `plan` |
| claude_md_path | string | 否 | - | CLAUDE.md 配置文件路径 |
| extra_args | string[] | 否 | [] | 传递额外的 CLI 参数 |
| allowed_tools | string[] | 否 | 全部 | 限制可用工具白名单 |
| env | object | 否 | {} | 环境变量（API Key 等） |

**权限模式说明**：

| 模式 | 行为 |
|------|------|
| `default` | 询问用户确认每个操作 |
| `acceptEdits` | 自动批准文件编辑，询问其他操作 |
| `bypassPermissions` | 完全自动执行（仅限受信任的工作目录） |
| `plan` | 仅规划不执行 |

#### 5.9.3 Claude Code SDK 集成

在环境中已集成 Claude Code SDK 的前提下，通过子进程调用 CLI 或直接使用 Anthropic SDK 实现 Agent：

```
                    ┌──────────────────────┐
                    │   AgentNodeFactory   │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        local Agent      http Agent      claudecode Agent
              │                │                │
              ▼                ▼                ▼
        LangChain         HTTP Client      ClaudeCodeRunner
        ReAct Agent                        │
                                    ┌──────┴──────┐
                                    ▼             ▼
                              CLI 模式       SDK 模式
                           (subprocess)   (anthropic SDK)
```

**CLI 模式**（推荐用于 v1，无需额外 SDK）：
```python
import asyncio
import json
import os
from typing import Dict, Any

class ClaudeCodeRunner:
    """Claude Code CLI 执行器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.work_dir = config.get("work_dir", os.getcwd())
        self.model = config.get("model", "claude-sonnet-4-6")
        self.max_turns = config.get("max_turns", 25)
        self.permission_mode = config.get("permission_mode", "acceptEdits")
        self.allowed_tools = config.get("allowed_tools", [])
        self.extra_args = config.get("extra_args", [])
        self.env = config.get("env", {})
    
    async def invoke(self, user_input: str, session_id: str, 
                     context: Dict[str, Any] = None) -> str:
        """通过 CLI 执行 Claude Code 任务"""
        
        # 构建 CLAUDE.md 临时内容（合并系统提示词 + 上下文）
        claude_md_content = self._build_claude_md(context)
        claude_md_path = self._write_temp_claude_md(claude_md_content, session_id)
        
        # 构建命令行参数
        cmd = [
            "claude",
            "--model", self.model,
            "--max-turns", str(self.max_turns),
            "--permission-mode", self.permission_mode,
            "--print",  # 非交互模式，直接输出结果
            "--output-format", "json",
            # 注入上下文
            "--custom-instructions", claude_md_path,
        ]
        
        # 添加工具白名单
        if self.allowed_tools:
            cmd.extend(["--allowed-tools", ",".join(self.allowed_tools)])
        
        cmd.extend(self.extra_args)
        
        # 执行
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.work_dir,
            env={**os.environ, **self.env}
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=user_input.encode("utf-8")),
            timeout=self.max_turns * 15  # 每轮估算 15 秒
        )
        
        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"Claude Code 执行失败 (code={process.returncode}): {error_msg}")
        
        # 解析输出
        output = stdout.decode("utf-8", errors="replace")
        try:
            result = json.loads(output)
            return result.get("result", output)
        except json.JSONDecodeError:
            return output
    
    def _build_claude_md(self, context: Dict[str, Any] = None) -> str:
        """构建 CLAUDE.md 内容"""
        parts = []
        if context and context.get("system_prompt"):
            parts.append(context["system_prompt"])
        if context and context.get("intermediate_results"):
            parts.append(f"\n## 上游结果\n{json.dumps(context['intermediate_results'], ensure_ascii=False, indent=2)}")
        return "\n".join(parts) if parts else ""
    
    def _write_temp_claude_md(self, content: str, session_id: str) -> str:
        """写入临时 CLAUDE.md"""
        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix=f"claude_md_{session_id}_")
        path = os.path.join(tmp_dir, "CLAUDE.md")
        if content:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        return path
```

**SDK 模式**（后续优化，利用 Anthropic SDK 直接调用）：
```python
# 当需要在工作流中更精细控制时，可通过 Anthropic SDK 构建
import anthropic

class ClaudeCodeSDKRunner:
    """基于 Anthropic SDK 的 Claude Code 执行器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.client = anthropic.Anthropic(api_key=config.get("api_key"))
        self.model = config.get("model", "claude-sonnet-4-6")
        self.max_turns = config.get("max_turns", 25)
        # 注册 Claude Code 原生工具
        self.tools = [
            # Read, Write, Edit, Bash, Grep, Glob 等工具定义
        ]
    
    async def invoke(self, user_input: str, context: Dict = None) -> str:
        """在使用 Anthropic SDK 的多轮对话循环中执行任务"""
        messages = [{"role": "user", "content": user_input}]
        
        for turn in range(self.max_turns):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=context.get("system_prompt", "") if context else "",
                messages=messages,
                tools=self.tools
            )
            
            # 处理工具调用
            if response.stop_reason == "tool_use":
                tool_results = await self._execute_tools(response.content)
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                return response.content[0].text
        
        raise RuntimeError(f"超过最大轮次 {self.max_turns}")
```

#### 5.9.4 Agent 表扩展

`agents` 表新增 `claudecode_config` 字段：

```sql
ALTER TABLE agents ADD COLUMN claudecode_config TEXT;
```

Agent 类型枚举扩展为：
```
agent_type: 'local' | 'http' | 'claudecode'
```

#### 5.9.5 工作流中的混用示例

```
工作流：代码审查 + 部署
├── 代码分析Agent（claudecode）
│   ├── 模型: Claude Sonnet 4.6
│   ├── 工作目录: /home/projects/myapp
│   └── 功能: 代码审查、性能分析
│
├── 数据库查询Agent（local）
│   ├── LLM: GPT-4o-mini
│   └── MCP: MySQL
│
└── 部署Agent（http）
    └── URL: http://deploy-system:8080/deploy
```

#### 5.9.6 Claude Code Agent 的 MCP 支持

Claude Code Agent 复用了平台已配置的 MCP Server，无需额外配置。Agent Factory 在创建 claudecode 节点时：
- 将 Agent 的 `mcp_servers` 配置传递给 Claude Code CLI 的 `--mcp-config`
- 或通过 Anthropic SDK 的工具注册机制加载

```python
def _build_mcp_args(self, mcp_servers: list) -> list:
    """将 MCP Server 配置转换为 Claude Code CLI 参数"""
    args = []
    for server in mcp_servers:
        if server.get("enabled", True):
            args.extend([
                "--mcp-config",
                json.dumps({
                    "name": server["name"],
                    "command": server["command"],
                    "args": server.get("args", []),
                    "env": server.get("env", {})
                })
            ])
    return args
```


