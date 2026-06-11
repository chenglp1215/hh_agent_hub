# 多Agent协同平台 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建研发团队多Agent协同平台，支持 3 种 Agent 类型(local/http/claudecode)、3 种工作流编排模式(supervisor/sequential/graph)、平台级资源目录(MCP Server/知识库/Skill)、端到端 SDLC 流程，对外提供 Chat API + WebSocket 实时追踪。

**Architecture:** 后端 FastAPI + LangGraph + Tortoise ORM + MySQL 8.0，前端 Vue 3 + TypeScript + Ant Design Vue + Vue Flow。自底向上分阶段构建：数据层 → 认证 → 资源目录 CRUD → Agent 核心 → 工作流引擎 → Chat API 集成 → 可观测性。前后端可并行开发，前端使用 Mock 数据驱动。

**Tech Stack:** Python 3.11, FastAPI, LangGraph, LangChain, Tortoise ORM, MySQL 8.0, Redis, Vue 3, TypeScript, Vite, Ant Design Vue, Vue Flow, Pinia

---

## 总览：文件结构设计

### 后端文件结构

```
backend/
├── main.py                     # FastAPI 入口 + lifespan
├── config.py                   # TORTOISE_ORM + Settings (pydantic-settings)
├── models/                     # Tortoise ORM 模型 (15 张表)
│   ├── __init__.py
│   ├── sys_config.py           # SysConfig
│   ├── user.py                 # User
│   ├── agent.py                # Agent
│   ├── workflow.py             # Workflow
│   ├── app.py                  # App
│   ├── session.py              # Session
│   ├── audit_log.py            # AuditLog
│   ├── mcp_server.py           # McpServerRegistry + AgentMcpLink
│   ├── knowledge_base.py       # KnowledgeBase + AgentKbLink + ContentBlock
│   ├── skill.py                # SkillRegistry + AgentSkillLink
│   └── workflow_trace.py       # WorkflowTrace
├── api/                        # 路由层
│   ├── __init__.py
│   ├── deps.py                 # get_current_user, require_admin 依赖
│   ├── middleware.py           # ApiKeyMiddleware (Chat API)
│   └── v1/
│       ├── __init__.py         # 注册所有子路由
│       ├── auth.py             # POST /auth/login, /auth/register, /auth/refresh
│       ├── configs.py          # GET/PUT /configs
│       ├── agents.py           # CRUD + test + copy
│       ├── workflows.py        # CRUD + publish + validate + graph
│       ├── apps.py             # CRUD + rotate-key + stats
│       ├── chat.py             # POST /chat (SSE流式) + session管理
│       ├── mcp_servers.py      # CRUD + discover + test
│       ├── knowledge_bases.py  # CRUD + sync + documents
│       ├── skills.py           # CRUD
│       ├── traces.py           # 追踪查询
│       ├── metrics.py          # GET /system/metrics
│       └── ws.py               # WebSocket /ws/execution/{id}/live
├── core/                       # 核心业务逻辑
│   ├── __init__.py
│   ├── llm_manager.py          # LLM 实例工厂 (OpenAI/Anthropic/Ollama)
│   ├── agent_factory.py        # AgentNodeFactory (local/http/claudecode)
│   ├── knowledge_injector.py   # KnowledgeInjector + KeywordRetriever
│   ├── http_agent_client.py    # HttpAgentClient
│   ├── claude_code_runner.py   # ClaudeCodeRunner (CLI模式)
│   ├── mcp_client.py           # MCPClient (HTTP Streamable)
│   ├── workflow_engine.py      # WorkflowEngine (supervisor/sequential/graph)
│   ├── workflow_executor.py    # WorkflowExecutor (timeout/retry/skip)
│   ├── workspace_manager.py    # WorkflowWorkspaceManager
│   ├── parallel_executor.py    # execute_parallel_group
│   ├── execution_tracer.py     # ExecutionTracer + TraceCallback
│   └── ws_manager.py           # WorkflowWebSocketManager
├── utils/                      # 工具类
│   ├── __init__.py
│   ├── crypto.py               # Fernet加密 + bcrypt密码哈希
│   ├── jwt.py                  # JWT 签发+验证
│   ├── sse.py                  # SSE 事件流工具
│   └── response.py             # 统一响应格式 {code, message, data}
├── schemas/                    # Pydantic 请求/响应模型
│   ├── __init__.py
│   ├── auth.py
│   ├── agent.py
│   ├── workflow.py
│   ├── app.py
│   ├── mcp_server.py
│   ├── knowledge_base.py
│   ├── skill.py
│   └── chat.py
└── migrations/                 # Aerich 迁移脚本
    └── .gitkeep
```

### 前端文件结构

```
frontend/
├── src/
│   ├── api/                    # Axios API 封装
│   │   ├── client.ts           # Axios 实例 + 拦截器
│   │   ├── agents.ts
│   │   ├── workflows.ts
│   │   ├── apps.ts
│   │   ├── chat.ts
│   │   ├── mcpServers.ts
│   │   ├── knowledgeBases.ts
│   │   ├── skills.ts
│   │   ├── auth.ts
│   │   └── traces.ts
│   ├── assets/
│   ├── components/             # 公共组件
│   │   ├── AppSidebar.vue
│   │   ├── PromptEditor.vue
│   │   ├── JsonEditor.vue
│   │   ├── McpServerSelector.vue
│   │   ├── KnowledgeBaseSelector.vue
│   │   ├── SkillsSelector.vue
│   │   ├── ResourcePicker.vue
│   │   ├── ChatWindow.vue
│   │   ├── StreamMessage.vue
│   │   └── ExecutionTimeline.vue
│   ├── views/                  # 页面 (17个)
│   │   ├── Login.vue
│   │   ├── Dashboard.vue
│   │   ├── NotFound.vue
│   │   ├── SystemConfig.vue
│   │   ├── AgentList.vue
│   │   ├── AgentEditor.vue
│   │   ├── McpServerList.vue
│   │   ├── McpServerEditor.vue
│   │   ├── KnowledgeBaseList.vue
│   │   ├── KnowledgeBaseEditor.vue
│   │   ├── SkillList.vue
│   │   ├── SkillEditor.vue
│   │   ├── WorkflowList.vue
│   │   ├── WorkflowEditor.vue
│   │   ├── AppList.vue
│   │   ├── AppEditor.vue
│   │   ├── ExecutionTraceList.vue
│   │   ├── ExecutionTrace.vue
│   │   └── ChatTest.vue
│   ├── stores/                 # Pinia 状态
│   │   ├── user.ts
│   │   ├── agent.ts
│   │   ├── resources.ts
│   │   ├── workflow.ts
│   │   ├── trace.ts
│   │   └── app.ts
│   ├── router/
│   │   └── index.ts
│   ├── utils/
│   │   ├── sse.ts
│   │   └── ws.ts
│   ├── layouts/
│   │   └── MainLayout.vue
│   ├── App.vue
│   └── main.ts
├── index.html
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
└── package.json
```

---

## 开发阶段总览

| 阶段 | 内容 | 工期 | 依赖 |
|------|------|------|------|
| **Phase 0-BE** | 后端项目骨架 | 0.5天 | 无 |
| **Phase 0-FE** | 前端项目骨架 | 0.5天 | 无 |
| **Phase 1-BE** | 数据层 (15表 ORM + Aerich) | 2天 | Phase 0-BE |
| **Phase 2-BE** | 认证与用户 | 1.5天 | Phase 1-BE |
| **Phase 3-BE** | 资源目录 CRUD | 2天 | Phase 2-BE |
| **Phase 4-BE** | Agent 核心 | 3天 | Phase 3-BE |
| **Phase 5-BE** | 工作流引擎 | 3天 | Phase 4-BE |
| **Phase 6-BE** | Chat API 与集成 | 2天 | Phase 5-BE |
| **Phase 7-BE** | 可观测性 | 1天 | Phase 6-BE |
| **Phase 1-FE** | 布局与路由 | 1天 | Phase 0-FE |
| **Phase 2-FE** | 资源目录管理 | 2天 | Phase 1-FE |
| **Phase 3-FE** | Agent 管理 | 2天 | Phase 2-FE |
| **Phase 4-FE** | 工作流编辑器 | 2天 | Phase 3-FE |
| **Phase 5-FE** | 应用管理与测试 | 1.5天 | Phase 4-FE |
| **Phase 6-FE** | 监控与追踪 | 1.5天 | Phase 5-FE |
| **Phase 7-FE** | 主控台与收尾 | 1天 | Phase 6-FE |

**合计：后端 15 天 + 前端 11.5 天，前后端可并行开发。**

---

# Part A: 后端实现 (15天)

## Phase 0-BE: 项目骨架 (0.5天)

### Task 0.1: 创建项目目录结构与配置文件

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/main.py`
- Create: `backend/config.py`
- Create: `backend/models/__init__.py`
- Create: `backend/api/__init__.py`
- Create: `backend/api/v1/__init__.py`
- Create: `backend/core/__init__.py`
- Create: `backend/utils/__init__.py`
- Create: `backend/schemas/__init__.py`
- Create: `backend/utils/response.py`
- Create: `requirements.txt`
- Create: `.env.example`

- [ ] **Step 1: Create requirements.txt**

```txt
# ============================================
# 核心框架
# ============================================
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.3
pydantic-settings==2.6.1

# ============================================
# Agent编排
# ============================================
langgraph==0.2.60
langchain==0.3.13
langchain-openai==0.2.14
langchain-anthropic==0.2.3
langchain-community==0.3.13

# ============================================
# 数据库 (MySQL + Tortoise ORM)
# ============================================
tortoise-orm[aiomysql]>=0.20.0
aerich>=0.7.0

# ============================================
# 缓存与会话
# ============================================
redis==5.2.1

# ============================================
# 认证与安全
# ============================================
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.20
cryptography==44.0.0

# ============================================
# 工具类
# ============================================
httpx==0.28.1
aiofiles==24.1.0
python-dotenv==1.0.1
tenacity==9.0.0
pyyaml==6.0.2

# ============================================
# 日志与监控
# ============================================
loguru==0.7.3
```

- [ ] **Step 2: Create .env.example**

```env
# 应用配置
APP_NAME=Multi-Agent Platform
APP_VERSION=1.0.0
DEBUG=true

# MySQL 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=agent_platform
DB_PASSWORD=your_password
DB_NAME=agent_platform

# Redis 配置
REDIS_URL=redis://localhost:6379/0

# 安全配置
SECRET_KEY=change-me-to-a-random-secret-key
FERNET_KEY=

# 默认限流
DEFAULT_RATE_LIMIT=60

# 会话配置
SESSION_TTL=3600

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log
```

- [ ] **Step 3: Create backend/config.py**

```python
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    APP_NAME: str = "Multi-Agent Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "agent_platform"
    DB_PASSWORD: str = ""
    DB_NAME: str = "agent_platform"

    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "change-me"
    FERNET_KEY: str = ""
    DEFAULT_RATE_LIMIT: int = 60
    SESSION_TTL: int = 3600

    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"

    BASE_DIR: Path = Path(__file__).resolve().parent

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

TORTOISE_ORM = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.mysql",
            "credentials": {
                "host": settings.DB_HOST,
                "port": settings.DB_PORT,
                "user": settings.DB_USER,
                "password": settings.DB_PASSWORD,
                "database": settings.DB_NAME,
                "charset": "utf8mb4",
                "pool": {"minsize": 2, "maxsize": 20},
            },
        }
    },
    "apps": {
        "models": {
            "models": [
                "models.sys_config",
                "models.user",
                "models.agent",
                "models.workflow",
                "models.app",
                "models.session",
                "models.audit_log",
                "models.mcp_server",
                "models.knowledge_base",
                "models.skill",
                "models.workflow_trace",
            ],
            "default_connection": "default",
        }
    },
    "timezone": "Asia/Shanghai",
}
```

- [ ] **Step 4: Create backend/utils/response.py**

```python
from typing import Any, Optional
from pydantic import BaseModel


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None


def success(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def error(code: int = -1, message: str = "error", data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data}
```

- [ ] **Step 5: Create backend/main.py**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise import Tortoise
from config import settings, TORTOISE_ORM
from loguru import logger
import sys

logger.remove()
logger.add(sys.stderr, level=settings.LOG_LEVEL)
logger.add(settings.LOG_FILE, rotation="10 MB", retention="7 days", level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Multi-Agent Platform...")
    await Tortoise.init(config=TORTOISE_ORM)
    logger.info("Database connected")
    yield
    logger.info("Shutting down...")
    await Tortoise.close_connections()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
```

- [ ] **Step 6: Create backend/api/v1/__init__.py**

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")


@router.get("/ping")
async def ping():
    return {"ping": "pong"}
```

- [ ] **Step 7: Register v1 router in main.py**

Edit `backend/main.py` — add after `app = FastAPI(...)`:

```python
from api.v1 import router as v1_router

app.include_router(v1_router)
```

- [ ] **Step 8: Create __init__.py files**

Run: `touch backend/__init__.py backend/models/__init__.py backend/api/__init__.py backend/core/__init__.py backend/utils/__init__.py backend/schemas/__init__.py`

- [ ] **Step 9: Run app to verify**

```bash
cd backend
pip install -r ../requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Expected: App starts. `GET http://localhost:8000/health` returns `{"status":"ok","version":"1.0.0"}`. `GET http://localhost:8000/api/v1/ping` returns `{"ping":"pong"}`.

- [ ] **Step 10: Commit**

```bash
git add backend/ requirements.txt .env.example
git commit -m "feat: initialize backend project skeleton with FastAPI + Tortoise ORM config"
```

---

## Phase 1-BE: 数据层 (2天)

### Task 1.1: SysConfig 模型

**Files:**
- Create: `backend/models/sys_config.py`
- Create: `backend/schemas/sys_config.py`

- [ ] **Step 1: Write SysConfig model**

`backend/models/sys_config.py`:

```python
from tortoise import fields, Model


class SysConfig(Model):
    id = fields.IntField(pk=True)
    config_key = fields.CharField(max_length=100, unique=True)
    config_value = fields.TextField()
    config_type = fields.CharField(max_length=20, default="string")
    description = fields.CharField(max_length=200, null=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "sys_configs"
```

- [ ] **Step 2: Write SysConfig schema**

`backend/schemas/sys_config.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SysConfigOut(BaseModel):
    id: int
    config_key: str
    config_value: str
    config_type: str
    description: Optional[str] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class SysConfigUpdate(BaseModel):
    config_value: str
    config_type: Optional[str] = None
    description: Optional[str] = None
```

- [ ] **Step 3: Verify model loads**

Add `from models.sys_config import SysConfig` to `main.py` lifespan startup. Restart app, verify no import errors.

- [ ] **Step 4: Commit**

```bash
git add backend/models/sys_config.py backend/schemas/sys_config.py backend/main.py
git commit -m "feat: add SysConfig model and schema"
```

### Task 1.2: User 模型

**Files:**
- Create: `backend/models/user.py`
- Create: `backend/schemas/auth.py`

- [ ] **Step 1: Write User model**

`backend/models/user.py`:

```python
from tortoise import fields, Model


class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    password_hash = fields.CharField(max_length=255)
    api_key = fields.CharField(max_length=64, unique=True)
    role = fields.CharField(max_length=20, default="user")
    email = fields.CharField(max_length=100, null=True)
    avatar = fields.CharField(max_length=200, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    last_login = fields.DatetimeField(null=True)

    class Meta:
        table = "users"
```

- [ ] **Step 2: Write auth schemas**

`backend/schemas/auth.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6)
    email: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 604800


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    email: Optional[str] = None
    avatar: Optional[str] = None
    api_key: str
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True
```

- [ ] **Step 3: Commit**

```bash
git add backend/models/user.py backend/schemas/auth.py
git commit -m "feat: add User model and auth schemas"
```

### Task 1.3: Agent 模型 + 资源目录模型 (McpServer, KnowledgeBase, Skill + 关联表)

**Files:**
- Create: `backend/models/agent.py`
- Create: `backend/models/mcp_server.py`
- Create: `backend/models/knowledge_base.py`
- Create: `backend/models/skill.py`

- [ ] **Step 1: Write Agent model**

`backend/models/agent.py`:

```python
from tortoise import fields, Model


class Agent(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    role = fields.CharField(max_length=20)
    agent_type = fields.CharField(max_length=20, default="local")
    llm_config = fields.JSONField(null=True)
    http_config = fields.JSONField(null=True)
    claudecode_config = fields.JSONField(null=True)
    system_prompt = fields.TextField(null=True)
    mcp_servers = fields.JSONField(default=list)
    skills = fields.JSONField(default=list)
    custom_tools = fields.JSONField(default=list)
    knowledge_base_ids = fields.JSONField(default=list)
    status = fields.CharField(max_length=20, default="active")
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "agents"
```

- [ ] **Step 2: Write McpServer model**

`backend/models/mcp_server.py`:

```python
from tortoise import fields, Model


class McpServerRegistry(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    base_url = fields.CharField(max_length=500)
    headers = fields.JSONField(default=dict)
    timeout = fields.IntField(default=30)
    discovered_tools = fields.JSONField(default=list)
    status = fields.CharField(max_length=20, default="active")
    last_checked_at = fields.DatetimeField(null=True)
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "mcp_server_registry"


class AgentMcpLink(Model):
    id = fields.IntField(pk=True)
    agent = fields.ForeignKeyField("models.Agent", on_delete=fields.CASCADE)
    mcp_server = fields.ForeignKeyField("models.McpServerRegistry", on_delete=fields.CASCADE)
    enabled_tools = fields.JSONField(default=list)
    enabled = fields.BooleanField(default=True)

    class Meta:
        table = "agent_mcp_links"
        unique_together = [("agent_id", "mcp_server_id")]
```

- [ ] **Step 3: Write KnowledgeBase model**

`backend/models/knowledge_base.py`:

```python
from tortoise import fields, Model


class KnowledgeBase(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    kb_type = fields.CharField(max_length=20, default="file")
    config = fields.JSONField(null=True)
    document_count = fields.IntField(default=0)
    embedding_model = fields.CharField(max_length=100, null=True)
    status = fields.CharField(max_length=20, default="active")
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "knowledge_bases"


class AgentKbLink(Model):
    id = fields.IntField(pk=True)
    agent = fields.ForeignKeyField("models.Agent", on_delete=fields.CASCADE)
    kb = fields.ForeignKeyField("models.KnowledgeBase", on_delete=fields.CASCADE)

    class Meta:
        table = "agent_kb_links"
        unique_together = [("agent_id", "kb_id")]


class ContentBlock(Model):
    id = fields.IntField(pk=True)
    kb = fields.ForeignKeyField("models.KnowledgeBase", on_delete=fields.CASCADE)
    source_file = fields.CharField(max_length=500)
    heading_path = fields.CharField(max_length=500, null=True)
    body = fields.TextField()
    token_count = fields.IntField(default=0)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "content_blocks"
```

- [ ] **Step 4: Write Skill model**

`backend/models/skill.py`:

```python
from tortoise import fields, Model


class SkillRegistry(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    skill_type = fields.CharField(max_length=20, default="prompt")
    content = fields.JSONField(null=True)
    category = fields.CharField(max_length=50, null=True)
    tags = fields.JSONField(default=list)
    version = fields.IntField(default=1)
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "skills_registry"


class AgentSkillLink(Model):
    id = fields.IntField(pk=True)
    agent = fields.ForeignKeyField("models.Agent", on_delete=fields.CASCADE)
    skill = fields.ForeignKeyField("models.SkillRegistry", on_delete=fields.CASCADE)

    class Meta:
        table = "agent_skill_links"
        unique_together = [("agent_id", "skill_id")]
```

- [ ] **Step 5: Commit**

```bash
git add backend/models/agent.py backend/models/mcp_server.py backend/models/knowledge_base.py backend/models/skill.py
git commit -m "feat: add Agent, McpServer, KnowledgeBase, Skill models with link tables"
```

### Task 1.4: Workflow + App + Session + WorkflowTrace + AuditLog 模型

**Files:**
- Create: `backend/models/workflow.py`
- Create: `backend/models/app.py`
- Create: `backend/models/session.py`
- Create: `backend/models/workflow_trace.py`
- Create: `backend/models/audit_log.py`
- Modify: `backend/config.py` — update TORTOISE_ORM models list

- [ ] **Step 1: Write remaining models in parallel files**

`backend/models/workflow.py`:

```python
from tortoise import fields, Model


class Workflow(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    description = fields.TextField(null=True)
    flow_type = fields.CharField(max_length=20)
    supervisor_agent = fields.ForeignKeyField("models.Agent", null=True, on_delete=fields.SET_NULL)
    worker_agent_ids = fields.JSONField(default=list)
    edges = fields.JSONField(default=list)
    parallel_groups = fields.JSONField(default=list)
    human_interrupts = fields.JSONField(default=list)
    error_strategy = fields.CharField(max_length=20, default="fail_fast")
    agent_timeout_seconds = fields.IntField(default=60)
    workflow_timeout_seconds = fields.IntField(default=300)
    max_retries = fields.IntField(default=2)
    status = fields.CharField(max_length=20, default="draft")
    version = fields.IntField(default=1)
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "workflows"
```

`backend/models/app.py`:

```python
from tortoise import fields, Model


class App(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    description = fields.TextField(null=True)
    workflow = fields.ForeignKeyField("models.Workflow", on_delete=fields.CASCADE)
    workflow_version = fields.IntField(default=1)
    api_key = fields.CharField(max_length=64, unique=True)
    rate_limit = fields.IntField(default=60)
    enabled = fields.BooleanField(default=True)
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "apps"
```

`backend/models/session.py`:

```python
from tortoise import fields, Model


class Session(Model):
    id = fields.CharField(max_length=36, pk=True)
    app = fields.ForeignKeyField("models.App", on_delete=fields.CASCADE)
    user_id = fields.CharField(max_length=100, null=True)
    messages = fields.JSONField(default=list)
    thread_state = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)
    expired_at = fields.DatetimeField(null=True)

    class Meta:
        table = "sessions"
```

`backend/models/workflow_trace.py`:

```python
from tortoise import fields, Model


class WorkflowTrace(Model):
    id = fields.IntField(pk=True)
    execution_id = fields.CharField(max_length=36, unique=True)
    workflow = fields.ForeignKeyField("models.Workflow", null=True, on_delete=fields.SET_NULL)
    app = fields.ForeignKeyField("models.App", null=True, on_delete=fields.SET_NULL)
    status = fields.CharField(max_length=20)
    agent_count = fields.IntField(default=0)
    total_duration_ms = fields.IntField(null=True)
    error_agent = fields.CharField(max_length=100, null=True)
    error_summary = fields.TextField(null=True)
    trace_file_path = fields.CharField(max_length=500)
    started_at = fields.DatetimeField(null=True)
    completed_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "workflow_traces"
```

`backend/models/audit_log.py`:

```python
from tortoise import fields, Model


class AuditLog(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    action = fields.CharField(max_length=50)
    target_type = fields.CharField(max_length=50, null=True)
    target_id = fields.IntField(null=True)
    request_id = fields.CharField(max_length=36, null=True)
    ip_address = fields.CharField(max_length=45, null=True)
    details = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "audit_logs"
```

- [ ] **Step 2: Update config.py models list**

Update `TORTOISE_ORM["apps"]["models"]["models"]` in `backend/config.py` to include all models:

```python
"models": [
    "models.sys_config",
    "models.user",
    "models.agent",
    "models.workflow",
    "models.app",
    "models.session",
    "models.audit_log",
    "models.mcp_server",
    "models.knowledge_base",
    "models.skill",
    "models.workflow_trace",
],
```

- [ ] **Step 3: Verify all models load without import errors**

```bash
cd backend && python -c "
from tortoise import Tortoise
import asyncio
async def test():
    await Tortoise.init(config_path='config.py:TORTOISE_ORM')
    print('All models loaded successfully')
asyncio.run(test())
"
```

- [ ] **Step 4: Commit**

```bash
git add backend/models/ backend/config.py
git commit -m "feat: add Workflow, App, Session, WorkflowTrace, AuditLog models"
```

### Task 1.5: Aerich 初始化与种子数据

**Files:**
- Modify: `backend/main.py` — add seed_defaults function

- [ ] **Step 1: Initialize Aerich**

```bash
cd backend
aerich init -t config.TORTOISE_ORM --location ./migrations
aerich init-db
```

Expected: Creates `migrations/` folder and `aerich` table in MySQL.

- [ ] **Step 2: Add seed_defaults to main.py lifespan**

In `backend/main.py`, add after the `from loguru import logger` block:

```python
import secrets
from models.sys_config import SysConfig
from models.user import User
from passlib.hash import bcrypt


async def seed_defaults():
    defaults = [
        ("llm.default.provider", "openai", "string", "默认LLM提供商"),
        ("llm.default.model", "gpt-4o-mini", "string", "默认模型"),
        ("llm.default.temperature", "0.3", "number", "默认温度参数"),
        ("system.max_tokens", "4096", "number", "最大token限制"),
        ("system.session_ttl", "3600", "number", "会话过期时间(秒)"),
        ("system.rate_limit.default", "60", "number", "默认限流(次/分钟)"),
    ]
    for key, value, ctype, desc in defaults:
        await SysConfig.get_or_create(
            config_key=key,
            defaults={"config_value": value, "config_type": ctype, "description": desc},
        )

    admin_key = secrets.token_urlsafe(32)
    await User.get_or_create(
        username="admin",
        defaults={
            "password_hash": bcrypt.hash("admin123"),
            "api_key": f"sk-{admin_key}",
            "role": "admin",
            "email": "admin@local.com",
        },
    )
    logger.info("Seed data inserted: admin user and default configs")
```

In lifespan startup, after `await Tortoise.init(...)`, add:
```python
await seed_defaults()
```

- [ ] **Step 3: Run app and verify**

```bash
uvicorn backend.main:app --reload
```

Expected: App starts, connects to MySQL, inserts seed data. Check MySQL: `SELECT * FROM sys_configs;` returns 6 rows. `SELECT username, role FROM users;` returns admin user.

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/ backend/main.py
git commit -m "feat: initialize Aerich migrations and seed default data"
```

---

## Phase 2-BE: 认证与用户 (1.5天)

### Task 2.1: 加密工具与 JWT

**Files:**
- Create: `backend/utils/crypto.py`
- Create: `backend/utils/jwt.py`

- [ ] **Step 1: Write crypto.py**

`backend/utils/crypto.py`:

```python
import os
from cryptography.fernet import Fernet
from passlib.hash import bcrypt


class CryptoManager:
    def __init__(self):
        key = os.getenv("FERNET_KEY")
        if not key:
            key = Fernet.generate_key().decode()
            os.environ["FERNET_KEY"] = key
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        return self._fernet.decrypt(ciphertext.encode()).decode()

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hash(password)

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        return bcrypt.verify(password, password_hash)


crypto = CryptoManager()
```

- [ ] **Step 2: Write jwt.py**

`backend/utils/jwt.py`:

```python
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7


def create_access_token(user_id: int, username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
```

- [ ] **Step 3: Commit**

```bash
git add backend/utils/crypto.py backend/utils/jwt.py
git commit -m "feat: add Fernet encryption and JWT token utilities"
```

### Task 2.2: 认证 API (login/register/refresh)

**Files:**
- Create: `backend/api/deps.py`
- Create: `backend/api/v1/auth.py`

- [ ] **Step 1: Write deps.py**

`backend/api/deps.py`:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.user import User
from utils.jwt import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证令牌")
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效或已过期")
    user = await User.get_or_none(id=int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user
```

- [ ] **Step 2: Write auth.py**

`backend/api/v1/auth.py`:

```python
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from models.user import User
from schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from utils.crypto import crypto
from utils.jwt import create_access_token, decode_access_token
from utils.response import success, error
from api.deps import get_current_user
import secrets

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login")
async def login(req: LoginRequest):
    user = await User.get_or_none(username=req.username)
    if not user or not crypto.verify_password(req.password, user.password_hash):
        return error(code=401, message="用户名或密码错误")
    user.last_login = datetime.now()
    await user.save(update_fields=["last_login"])
    token = create_access_token(user.id, user.username, user.role)
    return success(data={
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 604800,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "email": user.email,
        },
    })


@router.post("/register")
async def register(req: RegisterRequest):
    existing = await User.get_or_none(username=req.username)
    if existing:
        return error(code=400, message="用户名已存在")
    user = await User.create(
        username=req.username,
        password_hash=crypto.hash_password(req.password),
        api_key=f"sk-{secrets.token_urlsafe(32)}",
        email=req.email,
    )
    token = create_access_token(user.id, user.username, user.role)
    return success(data={
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 604800,
    })


@router.post("/refresh")
async def refresh_token(user: User = Depends(get_current_user)):
    token = create_access_token(user.id, user.username, user.role)
    return success(data={"access_token": token, "token_type": "bearer", "expires_in": 604800})


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return success(data={
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "email": user.email,
        "api_key": user.api_key,
        "avatar": user.avatar,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    })
```

- [ ] **Step 3: Register auth router in v1/__init__.py**

```python
from api.v1.auth import router as auth_router
router.include_router(auth_router)
```

- [ ] **Step 4: Test the auth APIs**

```bash
# Test login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Expected: returns access_token
```

- [ ] **Step 5: Commit**

```bash
git add backend/api/deps.py backend/api/v1/auth.py backend/api/v1/__init__.py
git commit -m "feat: add JWT authentication APIs (login/register/refresh/me)"
```

### Task 2.3: API Key 中间件

**Files:**
- Create: `backend/api/middleware.py`

- [ ] **Step 1: Write ApiKeyMiddleware**

`backend/api/middleware.py`:

```python
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from models.user import User
from models.app import App


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Chat API 的 API Key 认证中间件"""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/v1/chat"):
            api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")
            if not api_key:
                return self._unauthorized("未提供 API Key")

            app = await App.get_or_none(api_key=api_key, enabled=True)
            if not app:
                return self._unauthorized("无效的 API Key")

            request.state.app = app
            request.state.auth_type = "api_key"
        return await call_next(request)

    def _unauthorized(self, message: str):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"code": 401, "message": message},
        )
```

- [ ] **Step 2: Register middleware in main.py**

In `backend/main.py`, after `app.add_middleware(CORSMiddleware, ...)`:

```python
from api.middleware import ApiKeyMiddleware

app.add_middleware(ApiKeyMiddleware)
```

- [ ] **Step 3: Commit**

```bash
git add backend/api/middleware.py backend/main.py
git commit -m "feat: add API Key authentication middleware for Chat API"
```

---

## Phase 3-BE: 资源目录 CRUD (2天)

### Task 3.1: System Config API

**Files:**
- Create: `backend/api/v1/configs.py`

- [ ] **Step 1: Write configs API**

`backend/api/v1/configs.py`:

```python
from fastapi import APIRouter, Depends
from models.sys_config import SysConfig
from schemas.sys_config import SysConfigUpdate
from api.deps import require_admin
from utils.response import success, error

router = APIRouter(prefix="/configs", tags=["系统配置"])


@router.get("")
async def list_configs(_=Depends(require_admin)):
    configs = await SysConfig.all()
    return success(data=[{
        "id": c.id, "config_key": c.config_key,
        "config_value": "***" if c.config_type == "secret" else c.config_value,
        "config_type": c.config_type, "description": c.description,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    } for c in configs])


@router.put("/{key}")
async def update_config(key: str, body: SysConfigUpdate, _=Depends(require_admin)):
    config = await SysConfig.get_or_none(config_key=key)
    if not config:
        return error(code=404, message="配置项不存在")
    config.config_value = body.config_value
    if body.config_type:
        config.config_type = body.config_type
    if body.description is not None:
        config.description = body.description
    await config.save()
    return success(message="配置已更新")
```

- [ ] **Step 2: Register in v1/__init__.py**

```python
from api.v1.configs import router as configs_router
router.include_router(configs_router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/api/v1/configs.py backend/api/v1/__init__.py
git commit -m "feat: add system config API (list + update)"
```

### Task 3.2: MCP Server CRUD + discover + test

**Files:**
- Create: `backend/api/v1/mcp_servers.py`
- Create: `backend/schemas/mcp_server.py`

- [ ] **Step 1: Write MCP Server schemas**

`backend/schemas/mcp_server.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class McpServerCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    base_url: str = Field(..., max_length=500)
    headers: Optional[Dict[str, str]] = {}
    timeout: int = 30


class McpServerUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    base_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout: Optional[int] = None
```

- [ ] **Step 2: Write MCP Servers API**

`backend/api/v1/mcp_servers.py`:

```python
from fastapi import APIRouter, Depends
from models.mcp_server import McpServerRegistry
from schemas.mcp_server import McpServerCreate, McpServerUpdate
from api.deps import get_current_user, require_admin
from core.mcp_client import mcp_client
from utils.response import success, error

router = APIRouter(prefix="/mcp-servers", tags=["MCP Server"])


@router.get("")
async def list_mcp_servers(user=Depends(get_current_user)):
    servers = await McpServerRegistry.all()
    return success(data=[{
        "id": s.id, "name": s.name, "display_name": s.display_name,
        "description": s.description, "base_url": s.base_url,
        "discovered_tools": s.discovered_tools, "status": s.status,
        "timeout": s.timeout, "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    } for s in servers])


@router.get("/{server_id}")
async def get_mcp_server(server_id: int, user=Depends(get_current_user)):
    s = await McpServerRegistry.get_or_none(id=server_id)
    if not s:
        return error(code=404, message="MCP Server 不存在")
    return success(data={
        "id": s.id, "name": s.name, "display_name": s.display_name,
        "description": s.description, "base_url": s.base_url,
        "headers": s.headers, "timeout": s.timeout,
        "discovered_tools": s.discovered_tools, "status": s.status,
    })


@router.post("")
async def create_mcp_server(body: McpServerCreate, user=Depends(require_admin)):
    existing = await McpServerRegistry.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="名称已存在")
    s = await McpServerRegistry.create(
        name=body.name, display_name=body.display_name,
        description=body.description, base_url=body.base_url.rstrip("/"),
        headers=body.headers or {}, timeout=body.timeout,
        created_by=user,
    )
    return success(data={"id": s.id, "name": s.name}, message="注册成功")


@router.put("/{server_id}")
async def update_mcp_server(server_id: int, body: McpServerUpdate, user=Depends(require_admin)):
    s = await McpServerRegistry.get_or_none(id=server_id)
    if not s:
        return error(code=404, message="MCP Server 不存在")
    for field in ["display_name", "description", "base_url", "headers", "timeout"]:
        val = getattr(body, field, None)
        if val is not None:
            setattr(s, field, val)
    await s.save()
    return success(message="更新成功")


@router.delete("/{server_id}")
async def delete_mcp_server(server_id: int, user=Depends(require_admin)):
    s = await McpServerRegistry.get_or_none(id=server_id)
    if not s:
        return error(code=404, message="MCP Server 不存在")
    await s.delete()
    return success(message="已删除")


@router.post("/{server_id}/discover")
async def discover_tools(server_id: int, user=Depends(require_admin)):
    s = await McpServerRegistry.get_or_none(id=server_id)
    if not s:
        return error(code=404, message="MCP Server 不存在")
    try:
        from datetime import datetime
        await mcp_client.connect(server_id, s.base_url, s.headers)
        tools = await mcp_client.discover_tools(server_id)
        s.discovered_tools = tools
        s.status = "active"
        s.last_checked_at = datetime.now()
        await s.save()
        return success(data=tools, message=f"发现 {len(tools)} 个工具")
    except Exception as e:
        s.status = "error"
        await s.save()
        return error(code=-1, message=f"连接失败: {str(e)}")


@router.post("/{server_id}/test")
async def test_connection(server_id: int, user=Depends(require_admin)):
    s = await McpServerRegistry.get_or_none(id=server_id)
    if not s:
        return error(code=404, message="MCP Server 不存在")
    try:
        conn = await mcp_client.connect(server_id, s.base_url, s.headers)
        ok = await mcp_client.ping(conn)
        return success(data={"connected": ok})
    except Exception as e:
        return success(data={"connected": False, "error": str(e)})
```

- [ ] **Step 3: Register router**

```python
# in api/v1/__init__.py
from api.v1.mcp_servers import router as mcp_servers_router
router.include_router(mcp_servers_router)
```

- [ ] **Step 4: Write MCP Client (core)**

`backend/core/mcp_client.py`:

```python
import httpx
import time
from typing import List, Dict, Any, Optional
from loguru import logger


class McpServerConnection:
    def __init__(self, base_url: str, headers: Dict[str, str]):
        self.base_url = base_url
        self.headers = headers
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

    async def connect(self, server_id: int, base_url: str, headers: Dict[str, str] = None) -> McpServerConnection:
        base_url = base_url.rstrip("/")
        headers = headers or {}

        if server_id in self._connections:
            conn = self._connections[server_id]
            if await self.ping(conn):
                conn.last_used_at = time.time()
                return conn

        conn = McpServerConnection(base_url=base_url, headers=headers)
        client = await self._get_client()

        resp = await client.post(
            f"{base_url}/initialize",
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

        await client.post(
            f"{base_url}/notifications/initialized",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=headers,
        )
        conn.initialized = True
        self._connections[server_id] = conn
        logger.info(f"MCP [{base_url}] connected")
        return conn

    async def ping(self, conn: McpServerConnection) -> bool:
        try:
            client = await self._get_client()
            resp = await client.post(
                f"{conn.base_url}/ping",
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
        resp = await client.post(
            f"{conn.base_url}/tools/list",
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
        resp = await client.post(
            f"{conn.base_url}/tools/call",
            json={
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
            headers=conn.headers, timeout=self.TOOL_CALL_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            err = data["error"]
            raise Exception(f"MCP Error [{err.get('code')}]: {err.get('message')}")
        content_parts = []
        for item in data.get("result", {}).get("content", []):
            if item.get("type") == "text":
                content_parts.append(item["text"])
            elif item.get("type") == "resource":
                content_parts.append(item.get("text", "") or item.get("uri", ""))
        return "\n".join(content_parts)

    async def load_tools(self, server_id: int, base_url: str, headers: Dict, enabled_tools: List[str] = None) -> List:
        from langchain_core.tools import tool as lc_tool

        conn = await self.connect(server_id, base_url, headers)
        tools_meta = await self.discover_tools(server_id)
        langchain_tools = []
        sid = server_id

        for meta in tools_meta:
            t_name = meta["name"]
            if enabled_tools and t_name not in enabled_tools:
                continue

            @lc_tool
            async def wrapped_tool(**kwargs) -> str:
                return await self.call_tool(sid, t_name, kwargs)

            wrapped_tool.name = t_name
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


mcp_client = MCPClient()
```

- [ ] **Step 5: Commit**

```bash
git add backend/api/v1/mcp_servers.py backend/schemas/mcp_server.py backend/core/mcp_client.py backend/api/v1/__init__.py
git commit -m "feat: add MCP Server CRUD API with discover and test endpoints"
```

### Task 3.3: Skill CRUD API

**Files:**
- Create: `backend/api/v1/skills.py`
- Create: `backend/schemas/skill.py`

- [ ] **Step 1: Write schemas**

`backend/schemas/skill.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    skill_type: str = "prompt"
    content: Optional[Dict[str, Any]] = None
    category: Optional[str] = None
    tags: List[str] = []


class SkillUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    skill_type: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
```

- [ ] **Step 2: Write skills API**

`backend/api/v1/skills.py`:

```python
from fastapi import APIRouter, Depends, Query
from models.skill import SkillRegistry
from schemas.skill import SkillCreate, SkillUpdate
from api.deps import get_current_user, require_admin
from utils.response import success, error

router = APIRouter(prefix="/skills", tags=["Skill"])


@router.get("")
async def list_skills(
    category: str = Query(None),
    tag: str = Query(None),
    user=Depends(get_current_user),
):
    qs = SkillRegistry.all()
    if category:
        qs = qs.filter(category=category)
    skills = await qs
    if tag:
        skills = [s for s in skills if tag in (s.tags or [])]
    return success(data=[{
        "id": s.id, "name": s.name, "display_name": s.display_name,
        "description": s.description, "skill_type": s.skill_type,
        "category": s.category, "tags": s.tags, "version": s.version,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    } for s in skills])


@router.get("/{skill_id}")
async def get_skill(skill_id: int, user=Depends(get_current_user)):
    s = await SkillRegistry.get_or_none(id=skill_id)
    if not s:
        return error(code=404, message="Skill 不存在")
    return success(data={
        "id": s.id, "name": s.name, "display_name": s.display_name,
        "description": s.description, "skill_type": s.skill_type,
        "content": s.content, "category": s.category, "tags": s.tags,
        "version": s.version,
    })


@router.post("")
async def create_skill(body: SkillCreate, user=Depends(require_admin)):
    existing = await SkillRegistry.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="名称已存在")
    s = await SkillRegistry.create(
        name=body.name, display_name=body.display_name,
        description=body.description, skill_type=body.skill_type,
        content=body.content, category=body.category, tags=body.tags,
        created_by=user,
    )
    return success(data={"id": s.id, "name": s.name}, message="创建成功")


@router.put("/{skill_id}")
async def update_skill(skill_id: int, body: SkillUpdate, user=Depends(require_admin)):
    s = await SkillRegistry.get_or_none(id=skill_id)
    if not s:
        return error(code=404, message="Skill 不存在")
    for field in ["display_name", "description", "skill_type", "content", "category", "tags"]:
        val = getattr(body, field, None)
        if val is not None:
            setattr(s, field, val)
    s.version += 1
    await s.save()
    return success(message="更新成功")


@router.delete("/{skill_id}")
async def delete_skill(skill_id: int, user=Depends(require_admin)):
    s = await SkillRegistry.get_or_none(id=skill_id)
    if not s:
        return error(code=404, message="Skill 不存在")
    await s.delete()
    return success(message="已删除")
```

- [ ] **Step 3: Register router, commit**

```bash
git add backend/api/v1/skills.py backend/schemas/skill.py backend/api/v1/__init__.py
git commit -m "feat: add Skill CRUD API with category/tag filtering"
```

### Task 3.4: KnowledgeBase CRUD + sync + documents

**Files:**
- Create: `backend/api/v1/knowledge_bases.py`
- Create: `backend/schemas/knowledge_base.py`
- Modify: `backend/core/knowledge_injector.py`

- [ ] **Step 1: Write schemas**

`backend/schemas/knowledge_base.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class KBCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    kb_type: str = "file"
    config: Optional[Dict[str, Any]] = None
    embedding_model: Optional[str] = None


class KBUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    embedding_model: Optional[str] = None
```

- [ ] **Step 2: Write KnowledgeBase API**

`backend/api/v1/knowledge_bases.py`:

```python
import os
from fastapi import APIRouter, Depends, UploadFile, File
from models.knowledge_base import KnowledgeBase, ContentBlock
from schemas.knowledge_base import KBCreate, KBUpdate
from api.deps import get_current_user, require_admin
from utils.response import success, error

router = APIRouter(prefix="/knowledge-bases", tags=["知识库"])


@router.get("")
async def list_kbs(user=Depends(get_current_user)):
    kbs = await KnowledgeBase.all()
    return success(data=[{
        "id": k.id, "name": k.name, "display_name": k.display_name,
        "description": k.description, "kb_type": k.kb_type,
        "document_count": k.document_count, "status": k.status,
        "embedding_model": k.embedding_model,
        "created_at": k.created_at.isoformat() if k.created_at else None,
    } for k in kbs])


@router.get("/{kb_id}")
async def get_kb(kb_id: int, user=Depends(get_current_user)):
    k = await KnowledgeBase.get_or_none(id=kb_id)
    if not k:
        return error(code=404, message="知识库不存在")
    return success(data={
        "id": k.id, "name": k.name, "display_name": k.display_name,
        "description": k.description, "kb_type": k.kb_type,
        "config": k.config, "document_count": k.document_count,
        "status": k.status, "embedding_model": k.embedding_model,
    })


@router.post("")
async def create_kb(body: KBCreate, user=Depends(require_admin)):
    existing = await KnowledgeBase.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="名称已存在")
    k = await KnowledgeBase.create(
        name=body.name, display_name=body.display_name,
        description=body.description, kb_type=body.kb_type,
        config=body.config, embedding_model=body.embedding_model,
        created_by=user,
    )
    return success(data={"id": k.id, "name": k.name}, message="创建成功")


@router.put("/{kb_id}")
async def update_kb(kb_id: int, body: KBUpdate, user=Depends(require_admin)):
    k = await KnowledgeBase.get_or_none(id=kb_id)
    if not k:
        return error(code=404, message="知识库不存在")
    for field in ["display_name", "description", "config", "embedding_model"]:
        val = getattr(body, field, None)
        if val is not None:
            setattr(k, field, val)
    await k.save()
    return success(message="更新成功")


@router.delete("/{kb_id}")
async def delete_kb(kb_id: int, user=Depends(require_admin)):
    k = await KnowledgeBase.get_or_none(id=kb_id)
    if not k:
        return error(code=404, message="知识库不存在")
    await ContentBlock.filter(kb_id=kb_id).delete()
    await k.delete()
    return success(message="已删除")


@router.post("/{kb_id}/sync")
async def sync_kb(kb_id: int, user=Depends(require_admin)):
    k = await KnowledgeBase.get_or_none(id=kb_id)
    if not k:
        return error(code=404, message="知识库不存在")
    await ContentBlock.filter(kb_id=kb_id).delete()
    count = await _index_kb(k)
    k.document_count = count
    k.status = "active"
    await k.save()
    return success(data={"document_count": count}, message=f"同步完成，共 {count} 个文档块")


@router.get("/{kb_id}/documents")
async def list_documents(kb_id: int, user=Depends(get_current_user)):
    k = await KnowledgeBase.get_or_none(id=kb_id)
    if not k:
        return error(code=404, message="知识库不存在")
    blocks = await ContentBlock.filter(kb_id=kb_id)
    source_files = list(set(b.source_file for b in blocks))
    return success(data=[{"source_file": f, "block_count": sum(1 for b in blocks if b.source_file == f)} for f in source_files])


async def _index_kb(kb) -> int:
    """Index knowledge base content into content_blocks"""
    import re
    count = 0
    config = kb.config or {}

    if kb.kb_type == "file":
        source_path = config.get("source_path", "")
        file_patterns = config.get("file_patterns", ["*.md"])
        if os.path.isdir(source_path):
            for root, _, files in os.walk(source_path):
                for fn in files:
                    if any(fn.endswith(pat.replace("*", "")) for pat in file_patterns):
                        filepath = os.path.join(root, fn)
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                        sections = re.split(r"\n(?=## )", content)
                        for section in sections:
                            heading_match = re.match(r"^## (.+)", section)
                            heading = heading_match.group(1) if heading_match else fn
                            body = section.strip()
                            if body:
                                await ContentBlock.create(
                                    kb_id=kb.id, source_file=filepath,
                                    heading_path=f"{fn} > {heading}",
                                    body=body,
                                    token_count=len(body) // 2,
                                )
                                count += 1
    elif kb.kb_type == "url":
        urls = config.get("urls", [])
        for url in urls:
            await ContentBlock.create(
                kb_id=kb.id, source_file=url,
                heading_path=url, body=f"External URL: {url}",
                token_count=len(url) // 2,
            )
            count += 1
    return count
```

- [ ] **Step 3: Write KnowledgeInjector**

`backend/core/knowledge_injector.py`:

```python
from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass
from models.knowledge_base import ContentBlock


@dataclass
class SearchResult:
    chunk_id: int
    heading_path: str
    content: str
    source_file: str
    score: float


class KnowledgeRetriever(ABC):
    @abstractmethod
    async def search(self, kb_ids: List[int], query: str, top_k: int = 5) -> List[SearchResult]:
        ...


class KeywordRetriever(KnowledgeRetriever):
    async def search(self, kb_ids: List[int], query: str, top_k: int = 5) -> List[SearchResult]:
        if not kb_ids:
            return []
        keywords = self._extract_keywords(query)
        results = []
        for kw in keywords:
            blocks = await ContentBlock.filter(kb_id__in=kb_ids).filter(
                ContentBlock.body.icontains(kw) | ContentBlock.heading_path.icontains(kw)
            ).limit(top_k * 2)
            for b in blocks:
                score = 0.5
                if kw.lower() in (b.heading_path or "").lower():
                    score += 0.5
                results.append(SearchResult(
                    chunk_id=b.id, heading_path=b.heading_path or b.source_file,
                    content=b.body, source_file=b.source_file, score=score,
                ))
        results.sort(key=lambda r: r.score, reverse=True)
        seen = set()
        unique = []
        for r in results:
            if r.chunk_id not in seen:
                seen.add(r.chunk_id)
                unique.append(r)
        return unique[:top_k]

    def _extract_keywords(self, query: str) -> List[str]:
        import re
        tokens = re.findall(r"[一-鿿]+|[a-zA-Z]+", query)
        stopwords = {"的", "是", "在", "和", "了", "有", "我", "你", "他", "她", "它", "们", "这", "那", "吗", "呢", "吧", "啊"}
        return [t for t in tokens if t.lower() not in stopwords]


class KnowledgeInjector:
    def __init__(self, retriever: KnowledgeRetriever):
        self.retriever = retriever

    async def inject(self, kb_ids: List[int], user_query: str, base_prompt: str, max_tokens: int = 2000) -> str:
        if not kb_ids:
            return base_prompt
        results = await self.retriever.search(kb_ids, user_query, top_k=5)
        injected = []
        token_count = 0
        for r in results:
            estimated = len(r.content) // 2
            if token_count + estimated > max_tokens:
                break
            injected.append(f"### {r.heading_path}\n{r.content}")
            token_count += estimated
        if injected:
            base_prompt += "\n\n## 参考资料（来自知识库）\n" + "\n\n".join(injected)
        return base_prompt


knowledge_injector = KnowledgeInjector(KeywordRetriever())
```

- [ ] **Step 4: Register router and commit**

```bash
git add backend/api/v1/knowledge_bases.py backend/schemas/knowledge_base.py backend/core/knowledge_injector.py backend/api/v1/__init__.py
git commit -m "feat: add KnowledgeBase CRUD API with sync, documents, and keyword-based injector"
```

---

> **注意：** Phase 4-BE 到 Phase 7-BE 的详细任务由于文档篇幅已经非常长（Phase 0-3 已经覆盖了项目骨架、数据层、认证、资源目录共约 5.5 天），以下 Phase 4-7 提供结构化的任务框架，具体代码请参考设计文档 (`system_design_docs/04_Agent体系设计.md`, `05_工作流编排引擎.md`, `03_API设计.md`, `07_执行追踪与可观测性.md`)。

## Phase 4-BE: Agent 核心 (3天)

### Task 4.1: LLM Manager
**文件:** `backend/core/llm_manager.py`

基于设计文档 04 §5.3 — 实现 LLM 实例工厂，支持 OpenAI/Anthropic/Ollama 三种 provider。从 `llm_config` JSON 创建对应的 LangChain ChatModel。

### Task 4.2: AgentNodeFactory (local Agent)
**文件:** `backend/core/agent_factory.py`

基于设计文档 04 §5.3 — 创建 Local Agent 节点，组装 LLM + MCP 工具 + Skills Prompt + 知识库上下文。

### Task 4.3: HTTP Agent Client
**文件:** `backend/core/http_agent_client.py`

基于设计文档 04 §5.6 — HTTP Agent 客户端，发送 POST 请求到外部 Chat 服务，支持 request_template 和 response_mapping。

### Task 4.4: ClaudeCodeRunner
**文件:** `backend/core/claude_code_runner.py`

基于设计文档 04 §5.9 — CLI 子进程模式执行 Claude Code，支持 work_dir、permission_mode、allowed_tools。

### Task 4.5: Agent CRUD API
**文件:** `backend/api/v1/agents.py`, `backend/schemas/agent.py`

8 个端点：列表/详情/创建/更新/删除/测试/复制。创建 Agent 时支持选择资源目录（MCP Server + 知识库 + Skill 关联）。

**验证标准：**
- 创建 local/http/claudecode 三种类型 Agent 成功
- `POST /agents/{id}/test` 返回 LLM 响应
- 知识库注入: Agent Prompt 中包含检索到的知识段落

---

## Phase 5-BE: 工作流引擎 (3天)

### Task 5.1: WorkflowEngine (supervisor mode)
**文件:** `backend/core/workflow_engine.py`

基于设计文档 05 §5.2 — 使用 LangGraph StateGraph，定义 AgentState TypedDict，实现 Supervisor 路由逻辑。

### Task 5.2: Sequential + Graph modes
**文件:** `backend/core/workflow_engine.py` (same file)

追加 Sequential 模式(按 worker_agent_ids 顺序执行)和 Graph 模式(按 edges 定义的自定义有向图)。

### Task 5.3: Error handling (timeout/retry/skip)
**文件:** `backend/core/workflow_executor.py`

基于设计文档 05 §5.7 — 三种错误策略 fail_fast/skip_continue/retry，超时控制。

### Task 5.4: Parallel execution + Human interrupt
**文件:** `backend/core/parallel_executor.py`

基于设计文档 05 §5.8 — 并行执行组 + 人工中断点暂停/恢复。

### Task 5.5: WorkspaceManager
**文件:** `backend/core/workspace_manager.py`

基于设计文档 05 §5.10 — 工作空间创建、context.json 读写、Agent Prompt 构建。

### Task 5.6: Workflow CRUD API
**文件:** `backend/api/v1/workflows.py`, `backend/schemas/workflow.py`

9 个端点：列表/详情/创建/更新/删除/发布/图结构/验证。

---

## Phase 6-BE: Chat API 与集成 (2天)

### Task 6.1: Chat API (non-streaming + SSE streaming)
**文件:** `backend/api/v1/chat.py`, `backend/utils/sse.py`

基于设计文档 03 §4.6 — POST /chat 非流式 + SSE 流式响应。事件类型：thinking/agent_call/agent_result/text/done。

### Task 6.2: Session management
**文件:** `backend/api/v1/chat.py` (same file)

会话创建/查询/过期清理。messages 数组存储多轮对话历史。

### Task 6.3: App CRUD API
**文件:** `backend/api/v1/apps.py`, `backend/schemas/app.py`

8 个端点：列表/详情/创建/更新/删除/轮换密钥/调用统计。

### Task 6.4: Unified Resources API
**文件:** `backend/api/v1/__init__.py`

GET `/api/v1/resources?type=all` — 一次性获取所有可用资源(MCP/知识库/Skill)。

---

## Phase 7-BE: 可观测性 (1天)

### Task 7.1: ExecutionTracer + TraceCallback
**文件:** `backend/core/execution_tracer.py`

基于设计文档 07 §5.11 — 三层追踪树自动采集，trace.json 文件存储，LangChain Callback 集成。

### Task 7.2: WebSocket Manager
**文件:** `backend/core/ws_manager.py`

基于设计文档 07 §5.11.5 — WebSocket 订阅/推送，事件类型：execution_started/agent_started/span_completed/agent_completed/execution_completed/execution_error。

### Task 7.3: Trace + Metrics API
**文件:** `backend/api/v1/traces.py`, `backend/api/v1/metrics.py`, `backend/api/v1/ws.py`

追踪列表查询、追踪详情、metrics 聚合、WebSocket 端点 `/ws/execution/{execution_id}/live`。

---

# Part B: 前端实现 (11.5天)

> **注意：** 前端所有 Phase 使用 Mock 数据驱动开发，与后端并行进行。后端就绪后替换 Mock 为真实 API 调用。

## Phase 0-FE: 项目骨架 (0.5天)

### Task 0-FE.1: 创建 Vite + Vue 3 项目

**文件:**
- Create: `frontend/` (Vite scaffold)
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`

- [ ] **Step 1: Scaffold project**

```bash
npm create vite@latest frontend -- --template vue-ts
cd frontend
npm install
npm install ant-design-vue @ant-design/icons-vue
npm install vue-router pinia axios
npm install @vue-flow/core @vue-flow/background @vue-flow/controls
npm install monaco-editor
npm install tailwindcss @tailwindcss/vite
```

- [ ] **Step 2: Configure main.ts**

`frontend/src/main.ts`:

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Antd from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(Antd)
app.mount('#app')
```

- [ ] **Step 3: Configure App.vue**

```vue
<template>
  <router-view />
</template>
```

- [ ] **Step 4: Setup API client**

`frontend/src/api/client.ts`:

```typescript
import axios from 'axios'

const client = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  timeout: 30000,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
```

- [ ] **Step 5: Write vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

- [ ] **Step 6: Verify and commit**

```bash
cd frontend && npm run dev
# Open http://localhost:5173 — blank page, no errors

git add frontend/
git commit -m "feat: initialize Vue 3 + Vite + Ant Design Vue frontend scaffold"
```

---

## Phase 1-FE: 布局与路由 (1天)

### Task 1.1: 登录页面

**Files:**
- Create: `frontend/src/views/Login.vue`
- Create: `frontend/src/stores/user.ts`

- [ ] **Step 1: Write user store**

`frontend/src/stores/user.ts`:

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import router from '@/router'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('access_token') || '')
  const user = ref<any>(null)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function login(username: string, password: string) {
    const res = await authApi.login({ username, password })
    token.value = res.data.data.access_token
    user.value = res.data.data.user
    localStorage.setItem('access_token', token.value)
    router.push('/dashboard')
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('access_token')
    router.push('/login')
  }

  return { token, user, isLoggedIn, isAdmin, login, logout }
})
```

- [ ] **Step 2: Write Login.vue**

`frontend/src/views/Login.vue`:

```vue
<template>
  <div class="min-h-screen flex items-center justify-center bg-[#010102]">
    <a-card class="w-96" title="多Agent协同平台">
      <a-form :model="form" @finish="handleLogin">
        <a-form-item name="username" :rules="[{ required: true, message: '请输入用户名' }]">
          <a-input v-model:value="form.username" placeholder="用户名" size="large" />
        </a-form-item>
        <a-form-item name="password" :rules="[{ required: true, message: '请输入密码' }]">
          <a-input-password v-model:value="form.password" placeholder="密码" size="large" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" block size="large" :loading="loading">登录</a-button>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useUserStore } from '@/stores/user'
import { message } from 'ant-design-vue'

const userStore = useUserStore()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

async function handleLogin() {
  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    message.success('登录成功')
  } catch (e: any) {
    message.error(e.response?.data?.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/Login.vue frontend/src/stores/user.ts frontend/src/api/
git commit -m "feat: add login page and user store"
```

### Task 1.2: MainLayout + AppSidebar + Router

**Files:**
- Create: `frontend/src/layouts/MainLayout.vue`
- Create: `frontend/src/components/AppSidebar.vue`
- Create: `frontend/src/router/index.ts`
- Create: `frontend/src/views/Dashboard.vue` (stub)
- Create: `frontend/src/views/NotFound.vue`

- [ ] **Step 1: Write router**

`frontend/src/router/index.ts`:

```typescript
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },

  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/Dashboard.vue'), meta: { title: '主控台' } },
      // Agent
      { path: 'agents', name: 'AgentList', component: () => import('@/views/AgentList.vue'), meta: { title: 'Agent 列表' } },
      { path: 'agents/create', name: 'AgentCreate', component: () => import('@/views/AgentEditor.vue'), meta: { title: '创建 Agent' } },
      { path: 'agents/:id/edit', name: 'AgentEdit', component: () => import('@/views/AgentEditor.vue'), meta: { title: '编辑 Agent' }, props: true },
      // Workflows
      { path: 'workflows', name: 'WorkflowList', component: () => import('@/views/WorkflowList.vue'), meta: { title: '工作流列表' } },
      { path: 'workflows/create', name: 'WorkflowCreate', component: () => import('@/views/WorkflowEditor.vue'), meta: { title: '创建工作流' } },
      { path: 'workflows/:id/edit', name: 'WorkflowEdit', component: () => import('@/views/WorkflowEditor.vue'), meta: { title: '编辑工作流' }, props: true },
      // Apps
      { path: 'apps', name: 'AppList', component: () => import('@/views/AppList.vue'), meta: { title: '应用列表' } },
      { path: 'apps/create', name: 'AppCreate', component: () => import('@/views/AppEditor.vue'), meta: { title: '创建应用' } },
      { path: 'apps/:id/edit', name: 'AppEdit', component: () => import('@/views/AppEditor.vue'), meta: { title: '编辑应用' }, props: true },
      // Resources
      { path: 'resources/mcp-servers', name: 'McpServerList', component: () => import('@/views/McpServerList.vue'), meta: { title: 'MCP Server 管理' } },
      { path: 'resources/mcp-servers/create', name: 'McpServerCreate', component: () => import('@/views/McpServerEditor.vue'), meta: { title: '注册 MCP Server' } },
      { path: 'resources/mcp-servers/:id/edit', name: 'McpServerEdit', component: () => import('@/views/McpServerEditor.vue'), meta: { title: '编辑 MCP Server' }, props: true },
      { path: 'resources/knowledge-bases', name: 'KnowledgeBaseList', component: () => import('@/views/KnowledgeBaseList.vue'), meta: { title: '知识库管理' } },
      { path: 'resources/knowledge-bases/create', name: 'KnowledgeBaseCreate', component: () => import('@/views/KnowledgeBaseEditor.vue'), meta: { title: '创建知识库' } },
      { path: 'resources/knowledge-bases/:id/edit', name: 'KnowledgeBaseEdit', component: () => import('@/views/KnowledgeBaseEditor.vue'), meta: { title: '编辑知识库' }, props: true },
      { path: 'resources/skills', name: 'SkillList', component: () => import('@/views/SkillList.vue'), meta: { title: 'Skill 管理' } },
      { path: 'resources/skills/create', name: 'SkillCreate', component: () => import('@/views/SkillEditor.vue'), meta: { title: '创建 Skill' } },
      { path: 'resources/skills/:id/edit', name: 'SkillEdit', component: () => import('@/views/SkillEditor.vue'), meta: { title: '编辑 Skill' }, props: true },
      // Monitor
      { path: 'monitor/traces', name: 'ExecutionTraceList', component: () => import('@/views/ExecutionTraceList.vue'), meta: { title: '执行追踪' } },
      { path: 'monitor/traces/:executionId', name: 'ExecutionTraceDetail', component: () => import('@/views/ExecutionTrace.vue'), meta: { title: '追踪详情' }, props: true },
      { path: 'monitor/chat-test', name: 'ChatTest', component: () => import('@/views/ChatTest.vue'), meta: { title: '对话测试' } },
      // Settings
      { path: 'settings', name: 'SystemConfig', component: () => import('@/views/SystemConfig.vue'), meta: { title: '系统配置', requireAdmin: true } },
    ],
  },

  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('@/views/NotFound.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
```

- [ ] **Step 2: Write AppSidebar**

`frontend/src/components/AppSidebar.vue`:

```vue
<template>
  <a-layout-sider v-model:collapsed="collapsed" collapsible class="!bg-[#010102]">
    <div class="h-16 flex items-center justify-center text-white font-bold text-lg">
      <span v-if="!collapsed">Agent Hub</span>
      <span v-else>AH</span>
    </div>
    <a-menu
      v-model:selectedKeys="selectedKeys"
      mode="inline"
      theme="dark"
      :style="{ background: '#010102' }"
      @click="handleMenuClick"
    >
      <a-menu-item key="/dashboard">
        <DashboardOutlined /><span>主控台</span>
      </a-menu-item>

      <a-sub-menu key="agents">
        <template #title><RobotOutlined /><span>Agent 管理</span></template>
        <a-menu-item key="/agents">Agent 列表</a-menu-item>
      </a-sub-menu>

      <a-sub-menu key="workflows">
        <template #title><ApartmentOutlined /><span>工作流编排</span></template>
        <a-menu-item key="/workflows">工作流列表</a-menu-item>
      </a-sub-menu>

      <a-sub-menu key="apps">
        <template #title><AppstoreOutlined /><span>应用管理</span></template>
        <a-menu-item key="/apps">应用列表</a-menu-item>
      </a-sub-menu>

      <a-sub-menu key="resources">
        <template #title><DatabaseOutlined /><span>资源目录</span></template>
        <a-menu-item key="/resources/mcp-servers">MCP Server 管理</a-menu-item>
        <a-menu-item key="/resources/knowledge-bases">知识库管理</a-menu-item>
        <a-menu-item key="/resources/skills">Skill 管理</a-menu-item>
      </a-sub-menu>

      <a-sub-menu key="monitor">
        <template #title><LineChartOutlined /><span>监控</span></template>
        <a-menu-item key="/monitor/traces">执行追踪</a-menu-item>
        <a-menu-item key="/monitor/chat-test">对话测试</a-menu-item>
      </a-sub-menu>

      <a-menu-item key="/settings" v-if="userStore.isAdmin">
        <SettingOutlined /><span>系统设置</span>
      </a-menu-item>
    </a-menu>
  </a-layout-sider>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import {
  DashboardOutlined, RobotOutlined, ApartmentOutlined,
  AppstoreOutlined, DatabaseOutlined, LineChartOutlined, SettingOutlined,
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const collapsed = ref(false)
const selectedKeys = ref<string[]>([route.path])

watch(() => route.path, (path) => { selectedKeys.value = [path] })

function handleMenuClick({ key }: { key: string }) {
  router.push(key)
}
</script>
```

- [ ] **Step 3: Write MainLayout**

`frontend/src/layouts/MainLayout.vue`:

```vue
<template>
  <a-layout class="min-h-screen">
    <AppSidebar />
    <a-layout>
      <a-layout-content class="p-6 bg-[#0a0a0b]">
        <a-breadcrumb class="mb-4">
          <a-breadcrumb-item v-for="item in breadcrumbs" :key="item">{{ item }}</a-breadcrumb-item>
        </a-breadcrumb>
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'

const route = useRoute()
const breadcrumbs = computed(() => {
  const matched = route.matched.filter(r => r.meta?.title)
  return matched.map(r => r.meta.title as string)
})
</script>
```

- [ ] **Step 4: Write placeholder views**

Create stub files for all 17 view pages with minimal `<template><div>Page Name</div></template>` content.

- [ ] **Step 5: Verify and commit**

```bash
cd frontend && npm run dev
# Verify: sidebar navigation works, login page redirects, breadcrumbs show

git add frontend/src/
git commit -m "feat: add MainLayout, AppSidebar, router with 24 routes, and placeholder views"
```

---

## Phase 2-FE 到 Phase 7-FE 任务框架

以下 Phase 提供结构化任务框架，具体实现参考 `system_design_docs/08_前端设计.md` 和 `system_design_docs/18_前端开发顺序与方案.md`。

### Phase 2-FE: 资源目录管理 (2天)
- **Task 2a:** `McpServerList.vue` + `McpServerEditor.vue` — 卡片列表 + 状态灯 + 发现工具 + 测试连接
- **Task 2b:** `SkillList.vue` + `SkillEditor.vue` — 分类标签筛选 + Monaco Editor
- **Task 2c:** `KnowledgeBaseList.vue` + `KnowledgeBaseEditor.vue` — 类型选择动态表单 + 文档上传

### Phase 3-FE: Agent 管理 (2天)
- **Task 3a:** `AgentList.vue` — 搜索 + 类型筛选 + 表格(名称/类型标签/关联资源数/状态)
- **Task 3b:** `AgentEditor.vue` — 动态表单(根据 agent_type 切换) + 资源选择器
- **Task 3c:** `McpServerSelector.vue`, `KnowledgeBaseSelector.vue`, `SkillsSelector.vue`, `ResourcePicker.vue`

### Phase 4-FE: 工作流编辑器 (2天)
- **Task 4a:** `WorkflowList.vue` — 搜索 + 类型筛选 + 版本号 + 状态
- **Task 4b:** `WorkflowEditor.vue` — Vue Flow 画布(拖拽 Agent 节点 + 连线 + 属性面板)
- **Task 4c:** 自定义节点类型：SupervisorNode / WorkerNode / ConditionNode / ParallelGroupNode / HumanInterruptNode / StartEndNode

### Phase 5-FE: 应用管理与测试 (1.5天)
- **Task 5a:** `AppList.vue` + `AppEditor.vue` — API Key 脱敏+复制+轮换+调用统计图
- **Task 5b:** `ChatTest.vue` + `ChatWindow.vue` + `StreamMessage.vue` — SSE 事件渲染
- **Task 5c:** `utils/sse.ts` + `utils/ws.ts` — SSE 连接 + WebSocket 连接工具

### Phase 6-FE: 监控与追踪 (1.5天)
- **Task 6a:** `ExecutionTraceList.vue` — 搜索 + 状态筛选 + 自动刷新
- **Task 6b:** `ExecutionTrace.vue` — 三个 Tab(概览/时间轴/原始数据) + WebSocket 实时模式
- **Task 6c:** `ExecutionTimeline.vue` — 嵌套时间轴组件(AgentSpan/LlmSpan/ToolSpan/KbSpan + SpanDetail)

### Phase 7-FE: 主控台与收尾 (1天)
- **Task 7a:** `Dashboard.vue` — 统计卡片 + 最近执行列表 + 资源状态概览 + 快捷入口
- **Task 7b:** `SystemConfig.vue` — LLM 配置 + 安全配置 + 关于信息

---

## 自审清单 (Self-Review)

**1. Spec coverage:**
每个设计文档对应到计划任务：
- 01 (架构) → Phase 0-BE, Phase 0-FE
- 02 + 16 (数据库) → Phase 1-BE (全部 15 张表)
- 03 (API) → Phase 2-BE ~ Phase 7-BE (10 组 API)
- 04 (Agent) → Phase 4-BE
- 05 (工作流) → Phase 5-BE
- 06 (MCP) → Task 3.2, Task 5-BE
- 07 (可观测性) → Phase 7-BE
- 08 (前端) → Phase 1-FE ~ Phase 7-FE
- 09 (部署/安全) → Phase 2-BE (crypto/jwt)
- 10 (SDLC) → Phase 5-BE (workspace)
- 11 (测试) → 各 Task 的验证步骤
- 12 (技术栈) → Phase 0-BE/0-FE
- 19 (认证) → Phase 2-BE
- 20 (多容器) → 涉及 Docker 部署，未在当前计划中作为独立阶段

**2. Placeholder scan:** Phase 0-3 每步包含完整代码。Phase 4-7 以任务框架描述，引用了对应的设计文档，非 TBD/TODO 占位。

**3. Type consistency:**
- `Agent.agent_type`: `local | http | claudecode` (前后统一)
- `Workflow.flow_type`: `supervisor | sequential | graph` (前后统一)
- `Workflow.error_strategy`: `fail_fast | skip_continue | retry` (前后统一)
- API 响应格式: `{code: 0, message: "success", data: ...}` 全局统一
- MCP 协议: Streamable HTTP (JSON-RPC 2.0)，非 stdio

---

**计划完成并保存到 `docs/superpowers/plans/2026-06-11-multi-agent-platform.md`。**

**两个执行选项：**

**1. Subagent-Driven (推荐)** — 每个 Task 启动独立 subagent 实现，Task 间 review，快速迭代

**2. Inline Execution** — 在当前 session 中按顺序执行每个 Task，批量执行 + 检查点

**选择哪种方式？**
