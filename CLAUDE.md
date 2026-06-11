# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Multi-Agent Collaboration Platform** (研发团队多Agent协同平台) - An internal R&D team platform supporting:
- Multi-LLM configuration (OpenAI, Anthropic, Ollama)
- 3 Agent types: local (LangChain), http (remote), claudecode (Claude Code SDK)
- Platform resource catalog: MCP Server registry, Knowledge Base, Skill templates
- Multi-Agent workflow orchestration (supervisor, sequential, graph, parallel, human-interrupt)
- End-to-end SDLC pipeline (requirement → dev → test → deploy)
- Published workflows as applications with Chat API + WebSocket live trace

**Status**: Design phase only - no implementation code exists yet.

## Key Design Documents

All design docs are in `system_design_docs/`. Start from `system_design_docs/README.md` for the index.

| # | Document | Content |
|---|----------|---------|
| 01 | [项目概述与技术架构](system_design_docs/01_项目概述与技术架构.md) | Project overview, tech stack, architecture diagram |
| 02 | [数据库设计](system_design_docs/02_数据库设计.md) | 15 tables, ER diagram, schema definitions |
| 03 | [API设计](system_design_docs/03_API设计.md) | 10 API groups, request/response format |
| 04 | [Agent体系设计](system_design_docs/04_Agent体系设计.md) | 3 agent types, knowledge base injection, resource catalog |
| 05 | [工作流编排引擎](system_design_docs/05_工作流编排引擎.md) | LangGraph, error handling, parallel, workspace |
| 06 | [MCP协议与实现](system_design_docs/06_MCP协议与实现.md) | JSON-RPC, process lifecycle, tool discovery |
| 07 | [执行追踪与可观测性](system_design_docs/07_执行追踪与可观测性.md) | Trace tree, WebSocket, metrics, logging |
| 08 | [前端设计](system_design_docs/08_前端设计.md) | 16 pages, 8 components, UI mockups |
| 09 | [部署与安全](system_design_docs/09_部署与安全.md) | Docker, encryption, security |
| 10 | [SDLC流程](system_design_docs/10_SDLC端到端流程.md) | End-to-end R&D pipeline |
| 11 | [测试策略](system_design_docs/11_测试策略.md) | Test pyramid, mocks |
| 12 | [技术栈与项目结构](system_design_docs/12_技术栈与项目结构.md) | requirements.txt, dir structure, .env |
| 13 | [数据库迁移说明](system_design_docs/13_数据库迁移说明.md) | PostgreSQL → SQLite history |

## Technology Stack (Planned)

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11 + FastAPI |
| Agent Orchestration | LangGraph |
| LLM Integration | LangChain + Anthropic SDK |
| ORM | Tortoise ORM + aiomysql |
| Database | MySQL 8.0 (InnoDB, utf8mb4) |
| Migration | Aerich |
| Cache/Sessions | Redis |
| Frontend | Vue 3 + TypeScript + Vite + Ant Design Vue |
| Workflow Canvas | Vue Flow |
| Design System | Linear (DESIGN.md via getdesign.md) |

## Database: MySQL 8.0

- Character set: utf8mb4
- Engine: InnoDB
- Primary keys: INT AUTO_INCREMENT
- JSON fields: MySQL native JSON type
- Migration tool: Aerich (Tortoise ORM)
- Init: `aerich init -t backend.config.TORTOISE_ORM`

## Agent Configuration Schema

Agents store JSON fields:
- `llm_config`: `{provider, model, temperature, max_tokens, api_key, base_url}`
- `mcp_servers`: Array of `{name, command, args, env, enabled}`
- `skills`: Array of `{name, type, path/url/content, description}`
- `custom_tools`: Custom tool definitions

## Workflow Types

1. **Supervisor mode**: Supervisor agent routes tasks to worker agents
2. **Sequential mode**: Agents execute in pipeline order
3. **Graph mode**: Custom directed graph with conditional edges

## OpenSpec Workflow

This project uses spec-driven development:

```
/opsx:explore <topic>    → Think through ideas, investigate problems
/opsx:propose <name>     → Create proposal, design, and tasks
/opsx:apply <name>       → Execute tasks from the change
/opsx:archive <name>     → Archive completed change
```

**Important**: Explore mode is for thinking only - never implement features during explore.

## Multi-Agent Development

Invoke `/my-agents-info` to deploy a multi-agent development system:
- **planner**: Planning agent (sonnet, cyan)
- **backend-developer**: Backend development (sonnet, green)
- **frontend-developer**: Frontend development (sonnet, yellow)
- **verifier**: Code verification (haiku, purple)
- **tester**: Testing (haiku, red)

## Design System

This project follows the **Linear** design system. Before writing any UI code, read `DESIGN.md` for:
- Color tokens (dark near-black canvas, lavender-blue accent `#5e6ad2`, surface ladder)
- Typography scales (Linear Display/Text/Mono with specific tracking)
- Spacing and radius tokens
- Component patterns (buttons, cards, inputs, nav)

Key principles: dark-first, minimal chrome, single chromatic accent, product screenshots do the heavy lifting.

## Commands (When Implementation Starts)

```bash
# Setup
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
pip install -r requirements.txt

# Development server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Database backup
sqlite3 /data/agent_platform.db ".backup '/backup/agent_platform_$(date +%Y%m%d).db'"
```
