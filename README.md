# hh-agent-hub

**研发团队多 Agent 协同平台**

> 将研发工具链（MCP Server）、团队知识（知识库）、标准化流程（Skill）统一注册为平台级资源，研发人员通过配置 Agent + 编排工作流快速搭建智能助手应用，覆盖从问题排查到需求交付的全场景。

**一句话定位**：用 Agent 编排替代人工在多系统之间切换，让研发流程可自动化、可追踪、可复用。

---

## 核心功能

### 5 种 Agent 类型

| 类型 | 核心引擎 | 执行方式 | 典型场景 |
|------|---------|---------|---------|
| **local** | LangChain ReAct Agent | Worker 进程内 | 通用对话、MCP 工具调用 |
| **http** | HTTP Client | Worker 进程内 | 对接外部 Agent API、遗留系统 |
| **a2a** | A2A SDK (JSON-RPC) | Worker 进程内 | Agent 间通信、跨平台协作 |
| **claudecode** | Claude Code CLI | 独立 Docker 容器 | 代码分析、文件编辑、Git 操作 |
| **reasonix** | Reasonix CLI (DeepSeek) | 独立 Docker 容器 | 代码分析（低成本，只读） |

### 3 种编排模式

- **Supervisor 模式**：主管 Agent 根据任务内容动态路由到 Worker Agent，支持 4 套行为模板
- **Sequential 模式**：Agent 按固定顺序串行执行，上游结果传递下游
- **Graph 模式**：自定义有向图，支持条件分支和并行组

### 其他能力

- **平台资源目录**：MCP Server、知识库、Skill 统一注册管理
- **容器化执行**：claudecode/reasonix 在独立 Docker 容器中运行，用完即毁
- **Chat API + SSE**：工作流发布为应用，流式推送执行过程
- **企微机器人集成**：企微群聊/私聊触发工作流，支持定时任务
- **端到端 SDLC**：需求分析 → 方案设计 → 代码开发 → 审查 → 测试 → 部署

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Vite + Ant Design Vue + Vue Flow |
| 后端 | Python 3.11 + FastAPI |
| Agent 编排 | LangGraph + LangChain |
| LLM 接入 | LangChain + Anthropic SDK + claude-code-sdk |
| 数据库 | MySQL 8.0 (Tortoise ORM + Aerich) |
| 缓存/队列 | Redis |
| 容器化 | Docker SDK (docker-py) |
| 部署 | Docker Compose |

---

## 快速开始

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，设置数据库密码、API Key 等

# 2. 启动服务
docker compose up -d

# 3. 访问
# 前端: http://localhost:9020
# API:  http://localhost:9020/api/v1
```

### 常用命令

```bash
docker compose up -d              # 启动所有服务
docker compose up -d --build      # 重新构建并启动
docker compose ps                 # 查看服务状态
docker compose logs -f main       # 查看 main 服务日志
docker compose logs -f worker     # 查看 worker 日志
docker compose scale worker=3     # 扩展 worker 实例
docker compose down               # 停止服务
```

---

## 项目结构

```
hh_agent_hub/
├── backend/                # FastAPI 后端
│   ├── api/v1/             # REST API (10 个模块)
│   ├── core/               # 核心业务逻辑
│   │   ├── workflow_engine.py    # LangGraph 编排引擎
│   │   ├── agent_factory.py      # Agent 工厂
│   │   ├── llm_manager.py        # LLM 接入管理
│   │   ├── mcp_client.py         # MCP 协议客户端
│   │   └── wecom_bot/            # 企微机器人连接器
│   ├── models/             # Tortoise ORM 模型 (15 张表)
│   └── schemas/            # Pydantic 数据结构
├── frontend/               # Vue 3 前端
│   └── src/
│       ├── views/          # 页面 (16 个)
│       ├── components/     # 组件 (8 个)
│       └── api/            # API 调用层
├── worker/                 # 后台任务 (工作流执行)
├── system_design_docs/     # 系统设计文档 (20 篇)
└── docker-compose.yml      # 容器编排 (7 容器)
```

---

## 文档

### 设计文档

| 文档 | 内容 |
|------|------|
| [项目概述与技术架构](system_design_docs/01_项目概述与技术架构.md) | 技术栈、架构图、核心指标 |
| [数据库设计](system_design_docs/02_数据库设计.md) | 15 张表、ER 图 |
| [API 设计](system_design_docs/03_API设计.md) | 10 个 API 模块 |
| [Agent 体系设计](system_design_docs/04_Agent体系设计.md) | 5 种 Agent 类型详解 |
| [工作流编排引擎](system_design_docs/05_工作流编排引擎.md) | LangGraph 编排、错误处理 |
| [MCP 协议与实现](system_design_docs/06_MCP协议与实现.md) | JSON-RPC、工具发现 |
| [执行追踪与可观测性](system_design_docs/07_执行追踪与可观测性.md) | 三层追踪树、WebSocket |
| [前端设计](system_design_docs/08_前端设计.md) | 16 个页面、8 个组件 |
| [部署与安全](system_design_docs/09_部署与安全.md) | Docker、加密、安全 |
| [SDLC 端到端流程](system_design_docs/10_SDLC端到端流程.md) | 需求→部署全流程 |
| [系统必要性与竞品对比](system_design_docs/14_系统必要性与竞品对比.md) | 与 Dify/Coze 对比 |
| [多容器部署方案](system_design_docs/20_多容器部署方案.md) | 7 容器拓扑、通信机制 |

### 演示文稿

- [平台介绍 PPT](docs/hh-agent-hub-presentation.html)
- [工作流编排演示](docs/harness-vibecoding-intro.html)
- [项目介绍文档](docs/hh_agent_hub_overview.md)

---

## 适用场景

| 场景 | 适合 | 不适合 |
|------|------|--------|
| 有 MCP 工具链的研发团队 | 通用 ChatBot 平台 |
| 需要代码分析/编辑的 Agent | 纯对话客服系统 |
| 端到端 SDLC 自动化 | 单次简单问答 |
| 数据安全要求高（内网部署） | 无运维能力的小团队 |
| 多 Agent 协同的复杂流程 | 需要 GPU 推理的场景 |

---

## 与竞品对比

| 能力 | hh-agent-hub | Dify | Coze | LangFlow |
|------|:---:|:---:|:---:|:---:|
| 多 Agent 编排 | 3 种模式 | 基础 | 基础 | LangGraph |
| MCP 协议 | 完整 Client | 部分 | 不支持 | 部分 |
| 平台资源目录 | MCP/KB/Skill | 无 | 无 | 无 |
| Claude Code 集成 | 原生 CLI/SDK | 无 | 无 | 无 |
| 端到端 SDLC | 完整 pipeline | 无 | 无 | 无 |
| 数据不出内网 | 自托管 | 自托管 | 仅云端 | 自托管 |

---

## License

Internal Use Only
