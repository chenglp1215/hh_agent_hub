# hh-agent-hub：研发团队多 Agent 协同平台

## 一、系统简介

**hh-agent-hub** 是一个面向研发团队内部的多 Agent 协同平台，核心理念是：

> 将研发工具链（MCP Server）、团队知识（知识库）、标准化流程（Skill）统一注册为平台级资源，研发人员通过配置 Agent + 编排工作流快速搭建智能助手应用，覆盖从问题排查到需求交付的全场景。

**一句话定位**：用 Agent 编排替代人工在多系统之间切换，让研发流程可自动化、可追踪、可复用。

---

## 二、核心功能

### 2.1 五种 Agent 类型

| 类型 | 核心引擎 | 执行方式 | 典型场景 |
|------|---------|---------|---------|
| **local** | LangChain ReAct Agent | Worker 进程内 | 通用对话、MCP 工具调用 |
| **http** | HTTP Client | Worker 进程内 | 对接外部 Agent API、遗留系统 |
| **a2a** | A2A SDK (JSON-RPC) | Worker 进程内 | Agent 间通信、跨平台协作 |
| **claudecode** | Claude Code CLI | **独立 Docker 容器** | 代码分析、文件编辑、Git 操作 |
| **reasonix** | Reasonix CLI (DeepSeek) | **独立 Docker 容器** | 代码分析（低成本，只读） |

### 2.2 多 Agent 工作流编排

基于 LangGraph 实现三种编排模式：

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Supervisor 模式 │  │  Sequential 模式 │  │  Graph 模式      │
│                  │  │                  │  │                  │
│  主管 Agent 根据  │  │  Agent 按固定顺序 │  │  自定义有向图     │
│  任务内容动态路由 │  │  串行执行         │  │  支持条件分支     │
│  到 Worker Agent │  │  上游结果传递下游 │  │  支持并行组       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

额外能力：
- **并行组**：多个 Agent 同时执行，汇总结果
- **人工中断**：在关键节点暂停等待人工确认
- **工作空间接力**：Agent 间共享文件系统产物

### 2.3 平台资源目录

```
MCP Server 注册表 ─── Agent 按需选用，工具级粒度授权
知识库管理     ─── Markdown 分块 + 关键词检索，注入 Agent Prompt
Skill 模板库   ─── 标准化任务模板，沉淀团队经验
```

### 2.4 容器化 Agent 执行

claudecode 和 reasonix 类型采用 Docker 容器隔离执行：

```
Worker 容器                          临时 Agent 容器 (--rm)
┌──────────────────┐                ┌──────────────────┐
│ Git clone 代码    │  docker run   │ /workspace/      │
│ 写 CLAUDE.md     │ ──────────▶   │   .git/          │
│ 写 settings.json │  stdin pipe   │   CLAUDE.md      │
│ 路径转换         │ ◀──────────   │   项目源码        │
│ 捕获结果         │  stdout JSON  │ CLI 执行 → 销毁   │
└──────────────────┘                └──────────────────┘
```

### 2.5 Chat API + WebSocket 实时追踪

- **Chat API**：将工作流发布为应用，对外提供 REST 接口
- **SSE 流式**：实时推送 Agent 执行事件（thinking → agent_call → result → done）
- **三层追踪树**：workflow → agent → tool，完整记录执行链路

### 2.6 企业微信机器人集成

通过企微 aibot SDK 的 WebSocket 协议，将平台应用绑定到企微群聊/私聊，实现**对话触发指定应用工作流**。

```
企业微信群聊/私聊
       │
       │ 用户发消息
       ▼
┌─ 企微 aibot WS 连接器 ──────────────────────────────────────┐
│                                                              │
│  ① 收到消息 → 清理 @机器人 前缀                              │
│  ② 查找触发器映射: (chat_type, chat_id) → App               │
│  ③ 匹配成功 → 入队工作流任务                                 │
│  ④ 回复"正在思考..."（流式）                                 │
│  ⑤ 等待工作流结果（最长 5 分钟）                             │
│  ⑥ 用最终结果覆盖回复                                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌─ Worker ─────────┐
│ 工作流执行        │
│ Supervisor 路由   │
│ Agent 协同        │
└──────────────────┘
```

**核心特性**：

| 特性 | 说明 |
|------|------|
| **触发器绑定** | 将企微群/私聊绑定到指定 App，消息自动触发工作流 |
| **验证码绑定** | 在管理平台生成验证码，企微发送即可完成绑定，无需手动输入 ID |
| **多轮对话** | 维护同一聊天的 10 条消息历史窗口，支持上下文连续对话 |
| **流式回复** | 先回复"正在思考..."，工作流完成后用最终结果覆盖 |
| **定时触发** | 支持 interval/cron 两种定时方式（APScheduler），自动执行工作流 |
| **通知渠道** | 执行结果可通过企业微信 Webhook 推送到指定群 |
| **连接管理** | WebSocket 自动重连（无限重连），连接状态存 Redis 供前端展示 |

**触发器类型**：

```json
{
  "trigger_type": "wecom_bot",
  "wecom_chat_type": "group",
  "wecom_chat_id": "wrxxxxxxxx",
  "app_id": 1,
  "message": "请分析当前项目代码结构"
}
```

### 2.7 端到端 SDLC 流程

```
需求分析 Agent → 方案设计 Agent → 代码开发 Agent → 代码审查 Agent → 测试 Agent → CI/CD Agent
     │                │                │                │              │             │
     └────────────────┴────────────────┴────────────────┴──────────────┴─────────────┘
                              共享 workspace 接力，全流程可追踪
```

---

## 三、技术架构

### 3.1 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Ant Design Vue + Vue Flow |
| 后端 | Python 3.11 + FastAPI |
| Agent 编排 | LangGraph + LangChain |
| LLM 接入 | LangChain + Anthropic SDK + claude-code-sdk |
| 数据库 | MySQL 8.0 (Tortoise ORM + Aerich) |
| 缓存/队列 | Redis (会话、限流、任务队列) |
| 容器化 | Docker SDK (docker-py) |
| 部署 | Docker Compose (7 容器) |

### 3.2 容器拓扑

```
                         ┌──────────────────┐
                         │    Client         │
                         └────────┬─────────┘
                                  │ :9020
                                  ▼
┌──────────────────────────────────────────────────────────────┐
│  frontend (Nginx)                                            │
│  静态文件 + /api → main + /ws → main                         │
└───────────────────────────┬──────────────────────────────────┘
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  main        │  │  worker-1    │  │  worker-N    │
│  CRUD API    │  │  工作流执行   │  │  水平扩展    │
│  WebSocket   │  │  Agent 编排   │  │              │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │
       │          ┌──────┴──────┐
       │          ▼             ▼
       │  ┌──────────┐  ┌──────────────┐  ┌──────────────┐
       │  │  MySQL   │  │    Redis     │  │ wecom-bot    │
       │  └──────────┘  └──────────────┘  │ 企微 WS 连接  │
       │                                  └──────────────┘
       │  Worker 通过 Docker Socket 启动:
       ▼
┌─────────────────┐  ┌─────────────────┐
│ hh-claudecode   │  │ hh-reasonix     │
│ (临时容器 --rm)  │  │ (临时容器 --rm)  │
└─────────────────┘  └─────────────────┘
```

### 3.3 关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 数据库 | MySQL 8.0 | 团队熟悉，InnoDB 事务支持，utf8mb4 |
| Agent 编排 | LangGraph | 原生支持图结构、条件分支、并行 |
| Claude Code 执行 | 独立 Docker 容器 | 资源隔离、环境独立、用完即毁 |
| MCP 协议 | JSON-RPC over stdio | 标准化工具接入，进程级隔离 |
| 任务队列 | Redis BRPOP | 轻量、可靠、已有 Redis 基础设施 |
| 工作空间 | Bind Mount | Worker 容器和宿主机路径一致 |

---

## 四、系统优点

### 4.1 Agent 类型丰富，按需选择

五种 Agent 类型覆盖不同场景：本地 LLM 对话、远程 HTTP 调用、A2A 协议互通、Claude Code 代码操作、Reasonix 低成本分析。同一工作流可混用多种类型。

### 4.2 容器化执行，资源隔离

claudecode/reasonix agent 在独立 Docker 容器中执行：
- **隔离性**：一个 agent 崩溃不影响 worker 和其他 agent
- **资源控制**：内存/CPU 限制，防止资源耗尽
- **环境干净**：每次 `--rm` 创建销毁，无残留状态
- **镜像轻量**：~260MB，启动 <1 秒

### 4.3 平台级资源目录

MCP Server、知识库、Skill 统一注册管理，Agent 按需选用。避免每个 Agent 重复配置工具，实现资源复用和权限集中管控。

### 4.4 完整的执行追踪

三层追踪树（workflow → agent → tool）+ WebSocket 实时推送，执行过程完全透明。出现问题可快速定位到具体 Agent 和工具调用。

### 4.5 灵活的编排能力

Supervisor 动态路由、Sequential 流水线、Graph 自定义图，加上并行组和人工中断，能满足复杂研发流程的编排需求。

### 4.6 数据不出内网

完全自托管，Agent 代码、数据库 schema、告警日志等敏感数据不离开公司网络。LLM 调用可通过国内镜像代理。

---

## 五、系统缺点与局限

### 5.1 部署复杂度较高

7 个容器（frontend + main + worker×2 + mysql + redis + wecom-bot），加上 Agent 容器镜像需要单独构建。相比 Dify/Coze 的一键部署，运维成本更高。

### 5.2 依赖 Docker Socket

Worker 需要挂载宿主机的 `/var/run/docker.sock` 来启动 Agent 容器，这带来：
- 安全风险：Worker 对宿主机 Docker 有完全控制权
- 运维约束：Worker 必须和 Docker Daemon 在同一台宿主机

### 5.3 路径转换复杂

Worker 容器内路径和宿主机路径不同（bind mount），需要 `WORKSPACE_HOST_PATH` 环境变量做映射。如果配置错误，Agent 容器会看不到文件。

### 5.4 Reasonix 只读限制

Reasonix 的 `run` 模式不执行文件写入操作，只能用于代码分析/Review。代码编辑必须用 claudecode 类型，增加了用户理解成本。

### 5.5 缺乏可视化工作流编辑器

工作流配置目前通过 JSON/API 完成，虽然前端有 Vue Flow 画布组件，但工作流编辑器的完整交互尚未实现。对比 Dify 的拖拽式编辑，用户体验有差距。

### 5.6 LLM 调用成本不可控

多 Agent 工作流涉及多次 LLM 调用（Supervisor 路由 + Worker 执行），特别是 claudecode 类型的多轮工具调用，单次任务可能消耗大量 Token。缺乏细粒度的成本预算和超限熔断机制。

### 5.7 单点故障风险

- MySQL 单实例，宕机则全平台不可用
- Redis 单实例，任务队列和会话丢失
- Supervisor Agent 是工作流入口，其 LLM 调用失败则整个流程阻塞

### 5.8 水平扩展受限

Worker 可以水平扩展，但 Agent 容器必须在 Worker 所在宿主机上启动。跨主机扩展需要共享存储（NFS/分布式文件系统），当前方案不支持。

---

## 六、适用场景

| 场景 | 适合 | 不适合 |
|------|------|--------|
| 有 MCP 工具链的研发团队 | 通用 ChatBot 平台 |
| 需要代码分析/编辑的 Agent | 纯对话客服系统 |
| 端到端 SDLC 自动化 | 单次简单问答 |
| 数据安全要求高（内网部署） | 无运维能力的小团队 |
| 多 Agent 协同的复杂流程 | 需要 GPU 推理的场景 |

---

## 七、总结

hh-agent-hub 的核心价值在于：**把研发团队散落在各系统中的工具、知识、流程，通过 Agent 编排统一起来**。它不是通用 AI 平台的替代品，而是面向"有自建工具链（MCP）的研发团队"这个特定场景的解决方案。

容器化 Agent 执行（claudecode/reasonix）是区别于其他 Agent 平台的关键特性，它让 Agent 能真正操作代码仓库、执行命令、编辑文件，而不只是对话。

系统的主要挑战在于部署运维复杂度和成本控制，适合有 DevOps 能力的中大型研发团队使用。
