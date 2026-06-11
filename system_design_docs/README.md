# 研发团队多Agent协同平台 — 系统设计文档

## 文档版本
| 版本 | 日期 | 说明 |
|------|------|------|
| v2.0 | 2026-06-11 | 补充 P0 设计，拆分为分类文档 |

## 阅读指南

| 角色 | 推荐阅读顺序 |
|------|-------------|
| 新加入开发者 | `01 → 02 → 12 → 04 → 05 → 08` |
| 后端开发 | `02 → 03 → 04 → 05 → 06` |
| 前端开发 | `01 → 08 → 09` |
| 架构师 | `01 → 02 → 04 → 05 → 06 → 07` |
| DevOps | `09 → 12 → 13` |

## 文档索引

| # | 文档 | 内容 | 关键设计 |
|---|------|------|---------|
| 01 | [项目概述与技术架构](./01_项目概述与技术架构.md) | 项目背景、目标、核心指标、技术栈选型、整体架构图 | SQLite v1 策略，Linear 设计系统 |
| 02 | [数据库设计](./02_数据库设计.md) | 15 张表完整定义、ER 图、资源目录表、索引设计 | `mcp_server_registry`, `knowledge_bases`, `skills_registry`, `workflow_traces` |
| 03 | [API 设计](./03_API设计.md) | 10 组 API 端点，请求/响应格式，SSE 流式设计 | `/chat` 对话 API，`/mcp-servers/{id}/discover` |
| 04 | [Agent 体系设计](./04_Agent体系设计.md) | 三种 Agent 类型（local/http/claudecode），知识库检索注入，资源目录选择机制 | `KnowledgeInjector`, `KeywordRetriever`, Claude Code CLI/SDK |
| 05 | [工作流编排引擎](./05_工作流编排引擎.md) | LangGraph StateGraph 实现，监督者/顺序/图模式，错误处理，并行组，人工中断，工作空间接力 | `WorkflowWorkspaceManager`, `context.json` |
| 06 | [MCP 协议与实现](./06_MCP协议与实现.md) | JSON-RPC 2.0 协议细节，进程生命周期管理，工具发现，LangChain 适配 | 惰性启动，心跳检查，空闲回收 |
| 07 | [执行追踪与可观测性](./07_执行追踪与可观测性.md) | 三层追踪树，文件存储 + DB 元数据，WebSocket 实时推送，结构化日志，监控指标 | `ExecutionTracer`, `TraceCallback` |
| 08 | [前端设计](./08_前端设计.md) | 16 个页面 + 8 个组件，路由结构，Agent 编辑页（资源选择），工作流编辑器，追踪查看页 | Vue 3 + Ant Design Vue + Vue Flow |
| 09 | [部署与安全](./09_部署与安全.md) | Docker Compose，SQLite 备份，Fernet 加密，Prompt 注入防护，API 安全 | Docker + Nginx, WAL 模式 |
| 10 | [SDLC 端到端流程](./10_SDLC端到端流程.md) | 需求→设计→开发→测试→CICD 全流程，7 种 Agent 角色，工作流模板库 | 共享 workspace 接力模型 |
| 11 | [测试策略](./11_测试策略.md) | 测试金字塔，Agent 单测，工作流集成测试，MCP Mock Server | `MockMCPServer`, `TestAgentNode` |
| 12 | [技术栈与项目结构](./12_技术栈与项目结构.md) | requirements.txt，后端/前端目录结构，.env.example，启动命令 | Python 3.11 + FastAPI + LangGraph |
| 13 | [数据库选型说明](./13_数据库迁移说明.md) | MySQL 8.0 + Tortoise ORM + Aerich，选型历史 | 从 Pg→SQLite→MySQL 的变迁过程 |
| 14 | [系统必要性与竞品对比](./14_系统必要性与竞品对比.md) | 系统简介、必要性论证、与 Dify/Coze/LangFlow/OpenClaw 对比 | 差异化定位：研发全流程 Agent 平台 |
| 15 | [系统测试方案](./15_系统测试方案.md) | 4 阶段测试方案，69 条用例，CI/CD 集成，覆盖率目标 | MCP Mock，场景集成测试，性能基准 |
| 16 | [数据库与ORM模型](./16_数据库初始化与ORM模型.md) | 15 张表 Tortoise ORM 完整定义，Aerich 配置，init 脚本 | 完整 Model 代码, 种子数据, startup 初始化 |
| 17 | [后端开发顺序](./17_后端开发顺序与方案.md) | 7 阶段 15 天，每阶段产出 + 验证标准 + 依赖关系 | Phase 0 骨架 → Phase 7 可观测性 |
| 18 | [前端开发顺序](./18_前端开发顺序与方案.md) | 7 阶段 11.5 天，Mock 驱动，独立于后端开发 | Phase 0 骨架 → Phase 7 主控台 |
| 19 | [认证模块设计](./19_认证模块详细设计.md) | JWT 登录+刷新，API Key 中间件，权限矩阵，密码策略 | 双通道认证(管理端JWT + Chat端API Key) |
| 20 | [多容器部署方案](./20_多容器部署方案.md) | Docker Compose 5 容器，main+worker 拆分，Nginx 反代，扩缩策略 | Worker 独立执行工作流，水平可扩展 |

## 核心概念速查

| 概念 | 位置 | 说明 |
|------|------|------|
| Agent 类型 | 04 §5.3/5.6/5.9 | local (LangChain) / http (远程) / claudecode (Claude Code) |
| 资源目录 | 02 §3.3 | MCP Server、知识库、Skill 平台级注册 + Agent 按需选用 |
| 知识库检索 | 04 §5.5 | v1 Markdown 分块 + 关键词匹配，预留 Chroma 向量库 |
| 工作空间接力 | 05 §5.10 | 通用 workspace 模型，Engine 创建 + Agent 接力共享产物 |
| MCP 协议 | 06 §5.4 | JSON-RPC 2.0 over stdio，惰性启动/心跳/空闲回收 |
| 错误处理 | 05 §5.7 | fail-fast / skip-continue / retry 三种策略 |
| 执行追踪 | 07 §5.11 | 三层追踪树，trace.json 文件存储，WebSocket 实时推送 |
| context.json | 05 §5.10 | 工作流执行状态文件，Agent 间传递上下游摘要 |

## 外部资源

| 文件 | 用途 |
|------|------|
| `../DESIGN.md` | Linear 设计系统 tokens（颜色、字体、间距、组件） |
| `../CLAUDE.md` | 项目开发指南（技术栈、命令、设计系统引用） |
