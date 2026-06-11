# 数据库初始化与 ORM 模型设计

## 一、技术选型

| 层级 | 选型 | 说明 |
|------|------|------|
| 数据库 | MySQL 8.0 | InnoDB 引擎，utf8mb4 字符集 |
| ORM | Tortoise ORM >= 0.20 | 异步 ORM，原生 async/await |
| 驱动 | aiomysql | MySQL 异步驱动 |
| 迁移 | Aerich | Tortoise ORM 官方迁移工具 |

## 二、数据库配置

```python
# backend/config.py
TORTOISE_ORM = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.mysql",
            "credentials": {
                "host": "localhost",
                "port": 3306,
                "user": "agent_platform",
                "password": "your_password",
                "database": "agent_platform",
                "charset": "utf8mb4",
                "pool": {"minsize": 2, "maxsize": 20},
            }
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
                "models.agent_link",       # agent_mcp_links + agent_kb_links + agent_skill_links
            ],
            "default_connection": "default",
        }
    },
    "timezone": "Asia/Shanghai",
}
```

## 三、完整 ORM 模型定义

### 3.1 系统配置

```python
# models/sys_config.py
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

### 3.2 用户

```python
# models/user.py
from tortoise import fields, Model

class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    password_hash = fields.CharField(max_length=255)
    api_key = fields.CharField(max_length=64, unique=True)
    role = fields.CharField(max_length=20, default="user")  # admin / user
    email = fields.CharField(max_length=100, null=True)
    avatar = fields.CharField(max_length=200, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    last_login = fields.DatetimeField(null=True)

    # 反向关系
    agents: fields.ReverseRelation["Agent"]
    workflows: fields.ReverseRelation["Workflow"]
    apps: fields.ReverseRelation["App"]

    class Meta:
        table = "users"
```

### 3.3 Agent

```python
# models/agent.py
from tortoise import fields, Model

class Agent(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    role = fields.CharField(max_length=20)  # supervisor / worker
    agent_type = fields.CharField(max_length=20, default="local")  # local / http / claudecode
    llm_config = fields.JSONField(null=True)
    http_config = fields.JSONField(null=True)
    claudecode_config = fields.JSONField(null=True)
    system_prompt = fields.TextField(null=True)
    mcp_servers = fields.JSONField(default=list)     # Agent 自定义 MCP (补充)
    skills = fields.JSONField(default=list)           # Agent 自定义 Skill (补充)
    custom_tools = fields.JSONField(default=list)
    knowledge_base_ids = fields.JSONField(default=list)  # 关联 KB ID
    status = fields.CharField(max_length=20, default="active")

    # 外键
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    # 反向关系
    mcp_links: fields.ReverseRelation["AgentMcpLink"]
    kb_links: fields.ReverseRelation["AgentKbLink"]
    skill_links: fields.ReverseRelation["AgentSkillLink"]

    class Meta:
        table = "agents"
```

### 3.4 工作流

```python
# models/workflow.py
from tortoise import fields, Model

class Workflow(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    description = fields.TextField(null=True)
    flow_type = fields.CharField(max_length=20)  # supervisor / sequential / graph
    supervisor_agent = fields.ForeignKeyField("models.Agent", null=True, on_delete=fields.SET_NULL)
    worker_agent_ids = fields.JSONField(default=list)
    edges = fields.JSONField(default=list)
    parallel_groups = fields.JSONField(default=list)
    human_interrupts = fields.JSONField(default=list)
    error_strategy = fields.CharField(max_length=20, default="fail_fast")
    agent_timeout_seconds = fields.IntField(default=60)
    workflow_timeout_seconds = fields.IntField(default=300)
    max_retries = fields.IntField(default=2)
    status = fields.CharField(max_length=20, default="draft")  # draft / published / archived
    version = fields.IntField(default=1)

    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "workflows"
```

### 3.5 应用

```python
# models/app.py
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

    # 反向关系
    sessions: fields.ReverseRelation["Session"]

    class Meta:
        table = "apps"
```

### 3.6 会话

```python
# models/session.py
from tortoise import fields, Model

class Session(Model):
    id = fields.CharField(max_length=36, pk=True)  # UUID
    app = fields.ForeignKeyField("models.App", on_delete=fields.CASCADE)
    user_id = fields.CharField(max_length=100, null=True)
    messages = fields.JSONField(default=list)
    thread_state = fields.JSONField(null=True)  # LangGraph 线程状态

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)
    expired_at = fields.DatetimeField(null=True)

    class Meta:
        table = "sessions"
```

### 3.7 审计日志

```python
# models/audit_log.py
from tortoise import fields, Model

class AuditLog(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    action = fields.CharField(max_length=50)  # create / update / delete / call
    target_type = fields.CharField(max_length=50, null=True)
    target_id = fields.IntField(null=True)
    request_id = fields.CharField(max_length=36, null=True)
    ip_address = fields.CharField(max_length=45, null=True)
    details = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "audit_logs"
```

### 3.8 资源目录：MCP Server

```python
# models/mcp_server.py
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
    status = fields.CharField(max_length=20, default="active")  # active / disabled / error
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
    enabled_tools = fields.JSONField(default=list)  # 空=全部启用
    enabled = fields.BooleanField(default=True)

    class Meta:
        table = "agent_mcp_links"
        unique_together = [("agent_id", "mcp_server_id")]
```

### 3.9 资源目录：知识库

```python
# models/knowledge_base.py
from tortoise import fields, Model

class KnowledgeBase(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    kb_type = fields.CharField(max_length=20, default="file")  # file / url / rag
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

### 3.10 资源目录：Skill

```python
# models/skill.py
from tortoise import fields, Model

class SkillRegistry(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    skill_type = fields.CharField(max_length=20, default="prompt")  # prompt / file / url / mcp_skill
    content = fields.JSONField(null=True)
    category = fields.CharField(max_length=50, null=True)  # ops / development / testing / deployment
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

### 3.11 执行追踪

```python
# models/workflow_trace.py
from tortoise import fields, Model

class WorkflowTrace(Model):
    id = fields.IntField(pk=True)
    execution_id = fields.CharField(max_length=36, unique=True)
    workflow = fields.ForeignKeyField("models.Workflow", null=True, on_delete=fields.SET_NULL)
    app = fields.ForeignKeyField("models.App", null=True, on_delete=fields.SET_NULL)
    status = fields.CharField(max_length=20)  # running / success / failed / partial
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

## 四、Aerich 迁移配置

```bash
# 安装
pip install aerich

# 初始化 (项目根目录执行一次)
aerich init -t backend.config.TORTOISE_ORM --location backend/migrations

# 初始化数据库 (创建 aerich 迁移记录表)
aerich init-db

# 修改 Model 后生成迁移脚本
aerich migrate --name "add_content_blocks_table"

# 应用迁移
aerich upgrade

# 回滚
aerich downgrade

# 查看迁移历史
aerich history
```

```python
# backend/config.py 末尾追加 Aerich 配置
AERICH_CONFIG = {
    "apps": [{"models": {"models": [
        "models.sys_config", "models.user", "models.agent",
        "models.workflow", "models.app", "models.session",
        "models.audit_log", "models.mcp_server", "models.knowledge_base",
        "models.skill", "models.workflow_trace", "models.agent_link"
    ]}}],
    "location": "./backend/migrations",
}
```

## 五、app 启动初始化

```python
# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from tortoise import Tortoise
from config import TORTOISE_ORM
from loguru import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动：初始化 Tortoise ORM
    logger.info("Connecting to MySQL...")
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas(safe=True)  # 生产环境用 aerich migrate 替代

    logger.info("Database ready")

    # 插入种子数据
    await seed_defaults()

    yield

    # 关闭
    logger.info("Closing database connections...")
    await Tortoise.close_connections()


async def seed_defaults():
    """插入默认配置和 admin 用户"""
    from models.sys_config import SysConfig
    from models.user import User
    from utils.crypto import crypto

    # 默认系统配置
    defaults = [
        ("llm.default.provider", "openai", "string", "默认LLM提供商"),
        ("llm.default.model", "gpt-4o-mini", "string", "默认模型"),
        ("llm.default.temperature", "0.3", "number", "默认温度参数"),
        ("system.max_tokens", "4096", "number", "最大token限制"),
        ("system.session_ttl", "3600", "number", "会话过期时间(秒)"),
        ("system.rate_limit.default", "60", "number", "默认限流(次/分钟)"),
    ]
    for key, value, type_, desc in defaults:
        await SysConfig.get_or_create(
            config_key=key,
            defaults={"config_value": value, "config_type": type_, "description": desc}
        )

    # 默认 admin 用户
    import secrets
    admin_key = secrets.token_urlsafe(32)
    await User.get_or_create(
        username="admin",
        defaults={
            "password_hash": crypto.hash_password("admin123"),
            "api_key": f"sk-{admin_key}",
            "role": "admin",
            "email": "admin@local.com"
        }
    )
    logger.info("Seed data inserted")


app = FastAPI(lifespan=lifespan)
```

## 六、模型关系总图

```
User (1) ──────────── (N) Agent ─────────── (N) AgentMcpLink (N) ────── (1) McpServerRegistry
  │                       │
  │                       ├────────── (N) AgentKbLink (N) ───── (1) KnowledgeBase
  │                       │                                      │
  │                       ├────────── (N) AgentSkillLink (N) ─── (1) SkillRegistry
  │                       │                                      │
  │                       │                                      └── (1) ContentBlock (N)
  │                       │
  │                       ├─ supervisor ── (N) Workflow
  │                       │
  │                       │
  ├─ (1) ─────────── (N) Workflow
  │                       │
  │                       └── (1) ──────── (N) App
  │                                            │
  ├─ (1) ─────────── (N) App                   └── (1) ─── (N) Session
  │                       │
  │                       └── (1) ─── (N) WorkflowTrace
  │
  └─ (1) ─────────── (N) AuditLog
```
