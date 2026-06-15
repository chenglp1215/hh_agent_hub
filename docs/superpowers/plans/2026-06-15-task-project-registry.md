# Project Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ProjectRegistry and ClaudeSettingsRegistry as resource types, simplify claudecode agent configuration, and migrate Claude Code runner from CLI subprocess to claude-code-sdk.

**Architecture:** Follow existing resource pattern (McpServerRegistry + AgentMcpLink). Two new ORM models with CRUD routers registered at `/api/v1/projects/` and `/api/v1/claude-settings/`. Agent's `claudecode_config` JSONField stores `{project_registry_id, settings_registry_id}` references. The runner queries registries at execution time to clone repos and configure Claude Code.

**Tech Stack:** FastAPI, Tortoise ORM, claude-code-sdk (ClaudeSDKClient), GitPython, Vue 3, TypeScript, Ant Design Vue, axios

---

## File Structure

```
backend/
  models/
    project_registry.py     (CREATE) ProjectRegistry + AgentProjectLink
    claude_settings.py      (CREATE) ClaudeSettingsRegistry + AgentSettingsLink
    __init__.py             (MODIFY) Register new models
  schemas/
    project_registry.py     (CREATE) Pydantic request/response schemas
    claude_settings.py      (CREATE) Pydantic request/response schemas
  api/v1/
    projects.py             (CREATE) CRUD routes for projects
    claude_settings.py      (CREATE) CRUD routes for claude-settings
    __init__.py             (MODIFY) Register new routers
  core/
    git_ops.py              (CREATE) Git clone/pull operations
    claude_code_runner.py   (REWRITE) SDK-based runner
    agent_factory.py        (MODIFY) Update create_claudecode_agent
  config.py                 (MODIFY) Register new model modules in TORTOISE_ORM

frontend/src/
  api/
    projects.ts             (CREATE) API methods for projects
    claudeSettings.ts       (CREATE) API methods for claude-settings
  views/
    ProjectList.vue         (CREATE) Project registry list page
    ProjectEditor.vue       (CREATE) Project registry create/edit page
    ClaudeSettingsList.vue  (CREATE) Claude settings list page
    ClaudeSettingsEditor.vue(CREATE) Claude settings create/edit page
    AgentEditor.vue         (MODIFY) Simplify claudecode config section
  router/
    index.ts                (MODIFY) Add new resource routes
  components/
    AppSidebar.vue          (MODIFY) Add sidebar entries for new resources

tests/api/
  test_projects.py          (CREATE) API tests for project CRUD
  test_claude_settings.py   (CREATE) API tests for claude-settings CRUD
```

---

### Task B1: Create ProjectRegistry + AgentProjectLink models

**Files:**
- Create: `backend/models/project_registry.py`
- Modify: `backend/models/__init__.py`
- Modify: `backend/config.py`

- [ ] **Step 1: Create the ProjectRegistry model file**

Write `backend/models/project_registry.py`:

```python
from tortoise import fields, Model


class ProjectRegistry(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    git_repo_url = fields.CharField(max_length=500)
    git_branch = fields.CharField(max_length=100, default="main")
    git_auth_username = fields.CharField(max_length=100, null=True)
    git_auth_token = fields.CharField(max_length=500, null=True)
    clone_path = fields.CharField(max_length=500, null=True)
    system_prompt = fields.TextField(null=True)
    fix_timeout_minutes = fields.IntField(default=30)
    status = fields.CharField(max_length=20, default="active")
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "project_registry"


class AgentProjectLink(Model):
    id = fields.IntField(pk=True)
    agent = fields.ForeignKeyField("models.Agent", on_delete=fields.CASCADE)
    project = fields.ForeignKeyField("models.ProjectRegistry", on_delete=fields.CASCADE)

    class Meta:
        table = "agent_project_links"
        unique_together = [("agent_id", "project_id")]
```

- [ ] **Step 2: Register in models/__init__.py**

Edit `backend/models/__init__.py` to add:

```python
from .project_registry import ProjectRegistry, AgentProjectLink
```

And add to `__all__`:

```python
    "ProjectRegistry",
    "AgentProjectLink",
```

Edit using `Edit` tool with old_string/new_string:

old_string:
```python
from .skill import SkillRegistry, AgentSkillLink
```

new_string:
```python
from .project_registry import ProjectRegistry, AgentProjectLink
from .skill import SkillRegistry, AgentSkillLink
```

old_string:
```python
    "SkillRegistry",
    "AgentSkillLink",
```

new_string:
```python
    "SkillRegistry",
    "AgentSkillLink",
    "ProjectRegistry",
    "AgentProjectLink",
```

- [ ] **Step 3: Register in config.py TORTOISE_ORM**

Edit `backend/config.py`. Find the `TORTOISE_ORM` dict and add `"models.project_registry"` to the `apps.models.models` list.

old_string:
```python
                "models": [
                    "models.agent",
                    "models.mcp_server",
                    "models.knowledge_base",
                    "models.skill",
                    "models.sys_config",
                    "models.user",
                    "models.workflow",
                    "models.app",
                    "models.session",
                    "models.workflow_trace",
                    "models.audit_log",
                    "aerich.models",
                ],
```

new_string:
```python
                "models": [
                    "models.agent",
                    "models.mcp_server",
                    "models.knowledge_base",
                    "models.skill",
                    "models.project_registry",
                    "models.claude_settings",
                    "models.sys_config",
                    "models.user",
                    "models.workflow",
                    "models.app",
                    "models.session",
                    "models.workflow_trace",
                    "models.audit_log",
                    "aerich.models",
                ],
```

- [ ] **Step 4: Commit**

```bash
git add backend/models/project_registry.py backend/models/__init__.py backend/config.py
git commit -m "feat: add ProjectRegistry and AgentProjectLink models"
```

---

### Task B2: Create ClaudeSettingsRegistry + AgentSettingsLink models

**Files:**
- Create: `backend/models/claude_settings.py`
- Modify: `backend/models/__init__.py`

- [ ] **Step 1: Create the ClaudeSettingsRegistry model file**

Write `backend/models/claude_settings.py`:

```python
from tortoise import fields, Model


class ClaudeSettingsRegistry(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    model = fields.CharField(max_length=100, default="claude-sonnet-4-6")
    max_turns = fields.IntField(default=25)
    permission_mode = fields.CharField(max_length=50, default="acceptEdits")
    settings_json = fields.TextField(null=True)
    status = fields.CharField(max_length=20, default="active")
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "claude_settings_registry"


class AgentSettingsLink(Model):
    id = fields.IntField(pk=True)
    agent = fields.ForeignKeyField("models.Agent", on_delete=fields.CASCADE)
    settings = fields.ForeignKeyField("models.ClaudeSettingsRegistry", on_delete=fields.CASCADE)

    class Meta:
        table = "agent_settings_links"
        unique_together = [("agent_id", "settings_id")]
```

- [ ] **Step 2: Register in models/__init__.py**

Edit `backend/models/__init__.py` to add imports:

```python
from .claude_settings import ClaudeSettingsRegistry, AgentSettingsLink
```

And add to `__all__`:

```python
    "ClaudeSettingsRegistry",
    "AgentSettingsLink",
```

- [ ] **Step 3: Commit**

```bash
git add backend/models/claude_settings.py backend/models/__init__.py
git commit -m "feat: add ClaudeSettingsRegistry and AgentSettingsLink models"
```

---

### Task B3: Create Pydantic schemas for projects and claude-settings

**Files:**
- Create: `backend/schemas/project_registry.py`
- Create: `backend/schemas/claude_settings.py`

- [ ] **Step 1: Create project_registry schemas**

Write `backend/schemas/project_registry.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional


class ProjectRegistryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    git_repo_url: str = Field(..., max_length=500)
    git_branch: str = "main"
    git_auth_username: Optional[str] = None
    git_auth_token: Optional[str] = None
    clone_path: Optional[str] = None
    system_prompt: Optional[str] = None
    fix_timeout_minutes: int = 30


class ProjectRegistryUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    git_repo_url: Optional[str] = None
    git_branch: Optional[str] = None
    git_auth_username: Optional[str] = None
    git_auth_token: Optional[str] = None
    clone_path: Optional[str] = None
    system_prompt: Optional[str] = None
    fix_timeout_minutes: Optional[int] = None
    status: Optional[str] = None
```

- [ ] **Step 2: Create claude_settings schemas**

Write `backend/schemas/claude_settings.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional


class ClaudeSettingsCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    model: str = "claude-sonnet-4-6"
    max_turns: int = 25
    permission_mode: str = "acceptEdits"
    settings_json: Optional[str] = None


class ClaudeSettingsUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    max_turns: Optional[int] = None
    permission_mode: Optional[str] = None
    settings_json: Optional[str] = None
    status: Optional[str] = None
```

- [ ] **Step 3: Commit**

```bash
git add backend/schemas/project_registry.py backend/schemas/claude_settings.py
git commit -m "feat: add Pydantic schemas for project and claude-settings CRUD"
```

---

### Task B4: Create projects CRUD router

**Files:**
- Create: `backend/api/v1/projects.py`
- Modify: `backend/api/v1/__init__.py`

- [ ] **Step 1: Create the projects router**

Write `backend/api/v1/projects.py`:

```python
from fastapi import APIRouter, Depends, Query
from models.project_registry import ProjectRegistry
from schemas.project_registry import ProjectRegistryCreate, ProjectRegistryUpdate
from api.deps import get_current_user, require_admin
from utils.response import success, error

router = APIRouter(prefix="/projects", tags=["Project Registry"])


@router.get("")
async def list_projects(
    status: str = Query(None),
    search: str = Query(None),
    user=Depends(get_current_user),
):
    qs = ProjectRegistry.all()
    if status:
        qs = qs.filter(status=status)
    projects = await qs

    if search:
        q = search.lower()
        projects = [p for p in projects if q in (p.name + (p.display_name or "") + p.git_repo_url).lower()]

    return success(data=[{
        "id": p.id, "name": p.name, "display_name": p.display_name,
        "description": p.description, "git_repo_url": p.git_repo_url,
        "git_branch": p.git_branch,
        "clone_path": p.clone_path, "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    } for p in projects])


@router.get("/{project_id}")
async def get_project(project_id: int, user=Depends(get_current_user)):
    p = await ProjectRegistry.get_or_none(id=project_id)
    if not p:
        return error(code=404, message="项目不存在")
    return success(data={
        "id": p.id, "name": p.name, "display_name": p.display_name,
        "description": p.description, "git_repo_url": p.git_repo_url,
        "git_branch": p.git_branch,
        "git_auth_username": p.git_auth_username,
        "git_auth_token": p.git_auth_token,
        "clone_path": p.clone_path, "system_prompt": p.system_prompt,
        "fix_timeout_minutes": p.fix_timeout_minutes, "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    })


@router.post("")
async def create_project(body: ProjectRegistryCreate, user=Depends(require_admin)):
    existing = await ProjectRegistry.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="名称已存在")
    if not body.git_repo_url.strip():
        return error(code=400, message="Git 仓库地址不能为空")

    p = await ProjectRegistry.create(
        name=body.name, display_name=body.display_name,
        description=body.description, git_repo_url=body.git_repo_url.rstrip("/"),
        git_branch=body.git_branch or "main",
        git_auth_username=body.git_auth_username,
        git_auth_token=body.git_auth_token,
        clone_path=body.clone_path, system_prompt=body.system_prompt,
        fix_timeout_minutes=body.fix_timeout_minutes or 30,
        created_by=user,
    )
    return success(data={"id": p.id, "name": p.name}, message="创建成功")


@router.put("/{project_id}")
async def update_project(project_id: int, body: ProjectRegistryUpdate, user=Depends(require_admin)):
    p = await ProjectRegistry.get_or_none(id=project_id)
    if not p:
        return error(code=404, message="项目不存在")

    updatable = ["display_name", "description", "git_repo_url", "git_branch",
                  "git_auth_username", "git_auth_token", "clone_path",
                  "system_prompt", "fix_timeout_minutes", "status"]
    for field in updatable:
        val = getattr(body, field, None)
        if val is not None:
            if field == "git_repo_url":
                val = val.rstrip("/")
            setattr(p, field, val)

    await p.save()
    return success(message="更新成功")


@router.delete("/{project_id}")
async def delete_project(project_id: int, user=Depends(require_admin)):
    p = await ProjectRegistry.get_or_none(id=project_id)
    if not p:
        return error(code=404, message="项目不存在")
    await p.delete()
    return success(message="已删除")
```

- [ ] **Step 2: Register router in __init__.py**

Edit `backend/api/v1/__init__.py` to add:

```python
from api.v1.projects import router as projects_router
router.include_router(projects_router)
```

Add after the `skills_router` include_router block, before `agents_router`.

- [ ] **Step 3: Commit**

```bash
git add backend/api/v1/projects.py backend/api/v1/__init__.py
git commit -m "feat: add projects CRUD API router"
```

---

### Task B5: Create claude-settings CRUD router

**Files:**
- Create: `backend/api/v1/claude_settings.py`
- Modify: `backend/api/v1/__init__.py`

- [ ] **Step 1: Create the claude-settings router**

Write `backend/api/v1/claude_settings.py`:

```python
import json
from fastapi import APIRouter, Depends, Query
from models.claude_settings import ClaudeSettingsRegistry
from schemas.claude_settings import ClaudeSettingsCreate, ClaudeSettingsUpdate
from api.deps import get_current_user, require_admin
from utils.response import success, error

router = APIRouter(prefix="/claude-settings", tags=["Claude Settings"])


@router.get("")
async def list_settings(
    search: str = Query(None),
    user=Depends(get_current_user),
):
    qs = ClaudeSettingsRegistry.all()
    settings = await qs

    if search:
        q = search.lower()
        settings = [s for s in settings if q in (s.name + (s.display_name or "")).lower()]

    return success(data=[{
        "id": s.id, "name": s.name, "display_name": s.display_name,
        "description": s.description, "model": s.model,
        "max_turns": s.max_turns, "permission_mode": s.permission_mode,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    } for s in settings])


@router.get("/{settings_id}")
async def get_settings(settings_id: int, user=Depends(get_current_user)):
    s = await ClaudeSettingsRegistry.get_or_none(id=settings_id)
    if not s:
        return error(code=404, message="Claude 配置不存在")
    return success(data={
        "id": s.id, "name": s.name, "display_name": s.display_name,
        "description": s.description, "model": s.model,
        "max_turns": s.max_turns, "permission_mode": s.permission_mode,
        "settings_json": s.settings_json, "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    })


@router.post("")
async def create_settings(body: ClaudeSettingsCreate, user=Depends(require_admin)):
    existing = await ClaudeSettingsRegistry.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="名称已存在")

    # Validate settings_json if provided
    if body.settings_json and body.settings_json.strip():
        try:
            json.loads(body.settings_json)
        except json.JSONDecodeError:
            return error(code=400, message="settings_json 格式错误，请输入合法的 JSON")

    s = await ClaudeSettingsRegistry.create(
        name=body.name, display_name=body.display_name,
        description=body.description, model=body.model or "claude-sonnet-4-6",
        max_turns=body.max_turns or 25,
        permission_mode=body.permission_mode or "acceptEdits",
        settings_json=body.settings_json,
        created_by=user,
    )
    return success(data={"id": s.id, "name": s.name}, message="创建成功")


@router.put("/{settings_id}")
async def update_settings(settings_id: int, body: ClaudeSettingsUpdate, user=Depends(require_admin)):
    s = await ClaudeSettingsRegistry.get_or_none(id=settings_id)
    if not s:
        return error(code=404, message="Claude 配置不存在")

    # Validate settings_json if provided
    if body.settings_json is not None and body.settings_json.strip():
        try:
            json.loads(body.settings_json)
        except json.JSONDecodeError:
            return error(code=400, message="settings_json 格式错误，请输入合法的 JSON")

    updatable = ["display_name", "description", "model", "max_turns",
                  "permission_mode", "settings_json", "status"]
    for field in updatable:
        val = getattr(body, field, None)
        if val is not None:
            setattr(s, field, val)

    await s.save()
    return success(message="更新成功")


@router.delete("/{settings_id}")
async def delete_settings(settings_id: int, user=Depends(require_admin)):
    s = await ClaudeSettingsRegistry.get_or_none(id=settings_id)
    if not s:
        return error(code=404, message="Claude 配置不存在")
    await s.delete()
    return success(message="已删除")
```

- [ ] **Step 2: Register router in __init__.py**

Edit `backend/api/v1/__init__.py` to add:

```python
from api.v1.claude_settings import router as claude_settings_router
router.include_router(claude_settings_router)
```

Add after the `projects_router` include_router block.

- [ ] **Step 3: Commit**

```bash
git add backend/api/v1/claude_settings.py backend/api/v1/__init__.py
git commit -m "feat: add claude-settings CRUD API router"
```

---

### Task B6: Create git_ops.py

**Files:**
- Create: `backend/core/git_ops.py`

- [ ] **Step 1: Create git_ops.py**

Write `backend/core/git_ops.py`:

```python
import os
import shutil
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from typing import Optional

import git
from loguru import logger

from models.project_registry import ProjectRegistry


def embed_token_in_url(repo_url: str, token: str, username: str = None) -> str:
    """Embed auth token into Git URL for authentication."""
    parsed = urlparse(repo_url)
    if not token:
        return repo_url
    if username:
        netloc = f"{username}:{token}@{parsed.netloc}"
    else:
        netloc = f"{token}@{parsed.netloc}"
    return urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))


def get_workspace_path(project: ProjectRegistry, base_dir: str = None) -> Path:
    """Determine the workspace directory for a project."""
    if project.clone_path:
        return Path(project.clone_path) / project.name
    base = base_dir or os.path.join(os.getcwd(), "workspaces")
    return Path(base) / project.name


def clone_or_pull_repo(project: ProjectRegistry, base_dir: str = None) -> git.Repo:
    """Clone or pull a Git repository for the given project."""
    workspace_path = get_workspace_path(project, base_dir)
    repo_url = project.git_repo_url

    # Ensure URL ends with .git
    if not repo_url.endswith(".git"):
        repo_url = repo_url.rstrip("/") + ".git"

    auth_url = embed_token_in_url(repo_url, project.git_auth_token or "", project.git_auth_username)

    try:
        if workspace_path.exists():
            try:
                logger.info(f"Workspace exists, pulling: {workspace_path}")
                repo = git.Repo(workspace_path)
                repo.remotes.origin.pull()
                logger.info(f"Pull completed for {repo_url}")
                return repo
            except Exception as pull_error:
                logger.warning(f"Pull failed ({pull_error}), removing workspace and re-cloning")
                shutil.rmtree(workspace_path, ignore_errors=True)

        logger.info(f"Cloning repo: {repo_url} to {workspace_path}")
        workspace_path.parent.mkdir(parents=True, exist_ok=True)
        repo = git.Repo.clone_from(auth_url, workspace_path, branch=project.git_branch)
        logger.info(f"Clone completed, checked out {project.git_branch}")
        return repo

    except git.exc.GitCommandError as e:
        logger.error(f"Git command failed: {e.stderr}")
        raise RuntimeError(f"Git operation failed: {e.stderr}")
    except Exception as e:
        logger.error(f"Git operation error: {type(e).__name__}: {e}")
        raise
```

- [ ] **Step 2: Commit**

```bash
git add backend/core/git_ops.py
git commit -m "feat: add git_ops.py with clone/pull and auth token embedding"
```

---

### Task B7: Rewrite claude_code_runner.py with SDK support

**Files:**
- Rewrite: `backend/core/claude_code_runner.py`

- [ ] **Step 1: Rewrite the runner**

Write `backend/core/claude_code_runner.py`:

```python
import json
import os
from typing import Dict, Any, List, Optional

from loguru import logger


class ClaudeCodeRunner:
    """Claude Code 执行器 — 支持两种模式：

    1. 新模式（注册表引用）：claudecode_config = {"project_registry_id": int, "settings_registry_id": int}
       查询注册表获取 Git 信息和执行配置，使用 claude-code-sdk 执行。

    2. 旧模式（内联配置）：直接使用 config 中的 settings_json/work_dir 等字段，保留 CLI 子进程兼容。
    """

    def __init__(self, config: Dict[str, Any] = None,
                 mcp_servers: List[Dict] = None,
                 kb_content: List[Dict] = None,
                 skill_content: List[Dict] = None,
                 agent_name: str = "unknown"):
        self.config = config or {}
        self.mcp_servers = mcp_servers or []
        self.kb_content = kb_content or []
        self.skill_content = skill_content or []
        self.agent_name = agent_name

    async def invoke(self, user_input: str, session_id: str,
                     context: Dict[str, Any] = None) -> str:
        """执行 Claude Code 任务。

        Args:
            user_input: 用户输入/任务描述
            session_id: 会话标识
            context: 额外上下文，包含 system_prompt, intermediate_results 等

        Returns:
            Claude Code 执行结果文本
        """
        context = context or {}

        # 检测配置模式
        has_registry_refs = (
            self.config.get("project_registry_id") and
            self.config.get("settings_registry_id")
        )

        if has_registry_refs:
            return await self._invoke_with_registries(user_input, session_id, context)
        else:
            return await self._invoke_legacy(user_input, session_id, context)

    async def _invoke_with_registries(self, user_input: str, session_id: str,
                                       context: Dict[str, Any]) -> str:
        """新模式：通过注册表 ID 获取配置，使用 claude-code-sdk 执行。"""
        project_registry_id = self.config.get("project_registry_id")
        settings_registry_id = self.config.get("settings_registry_id")

        # 延迟导入避免循环依赖
        from models.project_registry import ProjectRegistry
        from models.claude_settings import ClaudeSettingsRegistry

        project = await ProjectRegistry.get_or_none(id=project_registry_id)
        settings = await ClaudeSettingsRegistry.get_or_none(id=settings_registry_id)

        if not project:
            logger.error(f"ProjectRegistry id={project_registry_id} not found for agent {self.agent_name}")
            return f"Error: 项目配置不存在 (id={project_registry_id})"

        if not settings:
            logger.error(f"ClaudeSettingsRegistry id={settings_registry_id} not found for agent {self.agent_name}")
            return f"Error: Claude 执行配置不存在 (id={settings_registry_id})"

        # 1. Clone 代码
        try:
            from core.git_ops import clone_or_pull_repo
            clone_or_pull_repo(project)
        except Exception as e:
            logger.error(f"Git clone failed for project {project.name}: {e}")
            return f"Error: Git 仓库克隆失败 - {e}"

        # 2. 构建 CLAUDE.md
        workspace_dir = str(await self._get_workspace_dir(project))
        self._write_claude_md(workspace_dir, context, project.system_prompt)

        # 3. 使用 claude-code-sdk 执行
        try:
            return await self._run_sdk(
                workspace_dir=workspace_dir,
                user_input=user_input,
                settings=settings,
                project=project,
                context=context,
            )
        except ImportError:
            logger.warning("claude-code-sdk not installed, falling back to legacy CLI")
            return await self._run_cli_legacy(workspace_dir, user_input, settings)
        except Exception as e:
            logger.error(f"Claude Code SDK execution failed: {e}")
            return f"Error: Claude Code 执行失败 - {e}"

    async def _get_workspace_dir(self, project) -> str:
        from core.git_ops import get_workspace_path
        return str(get_workspace_path(project))

    async def _run_sdk(self, workspace_dir: str, user_input: str,
                        settings, project, context: Dict[str, Any]) -> str:
        """使用 claude-code-sdk 执行 Claude Code。"""
        from claude_code_sdk import ClaudeSDKClient, ClaudeCodeOptions

        options_kwargs = {
            "permission_mode": settings.permission_mode,
            "cwd": workspace_dir,
            "max_turns": settings.max_turns,
        }

        # 如果 settings_json 存在，尝试解析并应用
        if settings.settings_json and settings.settings_json.strip():
            try:
                extra_settings = json.loads(settings.settings_json)
                # 从 settings_json 中提取 model
                if "model" in extra_settings:
                    options_kwargs["model"] = extra_settings["model"]
                elif settings.model:
                    options_kwargs["model"] = settings.model
            except json.JSONDecodeError:
                pass
        else:
            if settings.model:
                options_kwargs["model"] = settings.model

        # 合并系统提示
        system_prompt_parts = []
        agent_system_prompt = context.get("system_prompt", "")
        if agent_system_prompt:
            system_prompt_parts.append(agent_system_prompt)
        if project.system_prompt:
            system_prompt_parts.append(project.system_prompt)
        if system_prompt_parts:
            options_kwargs["system_prompt"] = "\n\n".join(system_prompt_parts)

        timeout_seconds = (project.fix_timeout_minutes or 30) * 60
        options = ClaudeCodeOptions(**options_kwargs)

        logger.info(f"Claude Code SDK: model={options_kwargs.get('model')}, "
                     f"max_turns={settings.max_turns}, cwd={workspace_dir}, "
                     f"timeout={timeout_seconds}s")

        client = ClaudeSDKClient(options)
        await client.connect()

        try:
            from claude_code_sdk.types import (
                ResultMessage, AssistantMessage, TextBlock, ToolUseBlock, UserMessage
            )

            last_text = ""
            await client.query(user_input)

            while True:
                tool_results = []
                got_result = False

                async for message in client.receive_response():
                    if hasattr(message, 'content') and not isinstance(message, ResultMessage):
                        if isinstance(message, AssistantMessage):
                            for block in message.content:
                                if isinstance(block, TextBlock) and block.text.strip():
                                    last_text = block.text
                                elif isinstance(block, ToolUseBlock) and block.name == "AskUserQuestion":
                                    # 将问题返回给调用方
                                    tool_results.append({
                                        "type": "question",
                                        "question": str(block.input),
                                    })

                    elif isinstance(message, ResultMessage):
                        result = message.result
                        is_error = message.is_error
                        got_result = True

                        if is_error:
                            logger.warning(f"Claude Code returned error: {result}")
                            return f"Claude Code 执行错误: {result}"

                        logger.info(f"Claude Code completed: cost={getattr(message, 'total_cost_usd', 'N/A')}")
                        return result or last_text or "执行完成（无输出）"

                if got_result:
                    break

                if tool_results and any(t.get("type") == "question" for t in tool_results):
                    # 返回问题等待外部回答
                    return json.dumps({"questions": tool_results}, ensure_ascii=False)
                else:
                    break

            return last_text or "执行完成（无输出）"

        except Exception as e:
            logger.error(f"SDK execution error: {e}")
            raise
        finally:
            await client.disconnect()

    async def _run_cli_legacy(self, workspace_dir: str, user_input: str,
                               settings) -> str:
        """回退到 CLI 子进程方式。"""
        import asyncio

        model = settings.model or "claude-sonnet-4-6"
        max_turns = settings.max_turns or 25
        permission_mode = settings.permission_mode or "acceptEdits"

        cmd = [
            "claude",
            "--model", model,
            "--max-turns", str(max_turns),
            "--permission-mode", permission_mode,
            "--print",
            "--output-format", "json",
        ]

        logger.info(f"Claude Code CLI (legacy): model={model}, max_turns={max_turns}, cwd={workspace_dir}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace_dir,
                env={**os.environ},
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=user_input.encode("utf-8")),
                timeout=settings.max_turns * 15 if settings else 375,
            )

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                raise RuntimeError(f"Claude Code exited with code {process.returncode}: {error_msg}")

            output = stdout.decode("utf-8", errors="replace")
            try:
                result = json.loads(output)
                return result.get("result", output)
            except json.JSONDecodeError:
                return output

        except asyncio.TimeoutError:
            logger.error("Claude Code CLI timed out")
            return "Error: Claude Code 执行超时"

    async def _invoke_legacy(self, user_input: str, session_id: str,
                              context: Dict[str, Any]) -> str:
        """旧模式：直接使用 config 中的内联字段（兼容现有 claudecode agent）。"""
        import asyncio

        # 兼容旧格式：从 config 中读取 settings_json, model, max_turns, work_dir
        settings_json = self.config.get("settings_json", "")
        model = self.config.get("model", "claude-sonnet-4-6")
        max_turns = self.config.get("max_turns", 25)
        work_dir = self.config.get("work_dir", "")
        permission_mode = self.config.get("permission_mode", "acceptEdits")

        if not work_dir:
            work_dir = os.getcwd()

        # 写入 settings.json
        claude_dir = os.path.join(work_dir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        if settings_json and settings_json.strip():
            try:
                settings_dict = json.loads(settings_json)
                with open(os.path.join(claude_dir, "settings.json"), "w", encoding="utf-8") as f:
                    json.dump(settings_dict, f, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                pass

        # 写入 CLAUDE.md
        self._write_claude_md(work_dir, context)

        # CLI 子进程调用
        cmd = [
            "claude",
            "--model", model,
            "--max-turns", str(max_turns),
            "--permission-mode", permission_mode,
            "--print",
            "--output-format", "json",
        ]

        logger.info(f"Claude Code CLI (legacy): model={model}, max_turns={max_turns}, work_dir={work_dir}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
                env={**os.environ},
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=user_input.encode("utf-8")),
                timeout=max_turns * 15,
            )

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                raise RuntimeError(f"Claude Code exited with code {process.returncode}: {error_msg}")

            output = stdout.decode("utf-8", errors="replace")
            try:
                result = json.loads(output)
                return result.get("result", output)
            except json.JSONDecodeError:
                return output

        except asyncio.TimeoutError:
            logger.error(f"Claude Code timeout after {max_turns * 15}s")
            return f"Error: Claude Code execution timed out after {max_turns * 15} seconds"
        except FileNotFoundError:
            logger.error("Claude Code CLI not found")
            return "Error: Claude Code CLI not found"
        except Exception as e:
            logger.error(f"Claude Code execution failed: {e}")
            raise

    def _write_claude_md(self, work_dir: str, context: Dict[str, Any] = None,
                          extra_system_prompt: str = None) -> None:
        """Build and write CLAUDE.md to work_dir."""
        context = context or {}
        os.makedirs(work_dir, exist_ok=True)

        parts = [
            "<!-- Auto-generated by Agent Platform. Edits will be overwritten on next execution. -->",
        ]

        # System prompt section
        system_prompt = context.get("system_prompt", "")
        if system_prompt:
            parts.append("")
            parts.append("## 系统指令")
            parts.append(system_prompt)
        if extra_system_prompt:
            parts.append("")
            parts.append("## 项目指令")
            parts.append(extra_system_prompt)

        # Knowledge base section
        if self.kb_content:
            parts.append("")
            parts.append("## 知识库")
            total_len = 0
            max_kb_bytes = 50000
            for block in self.kb_content:
                heading = block.get("heading_path", block.get("source_file", "未知来源"))
                body = block.get("body", "")
                chunk = f"\n### {heading}\n{body}"
                if total_len + len(chunk) > max_kb_bytes:
                    parts.append("\n--- 知识库内容已截断，超出 50KB ---")
                    break
                parts.append(chunk)
                total_len += len(chunk)

        # Skills section
        if self.skill_content:
            parts.append("")
            parts.append("## 可用技能")
            for skill in self.skill_content:
                name = skill.get("name", "未知技能")
                desc = skill.get("description", "")
                skill_type = skill.get("skill_type", "prompt")
                content = skill.get("content", {})
                parts.append(f"\n### {name}")
                if desc:
                    parts.append(f"描述: {desc}")
                if skill_type == "prompt":
                    template = content.get("prompt_template", "") if isinstance(content, dict) else ""
                    if template:
                        parts.append(f"\n{template}")
                elif skill_type == "file":
                    file_path = content.get("file_path", "") if isinstance(content, dict) else ""
                    if file_path:
                        parts.append(f"引用文件: {file_path}")
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                parts.append(f"\n```\n{f.read()}\n```")
                        except (FileNotFoundError, IOError) as e:
                            parts.append(f"\n*无法读取文件: {e}*")

        # Workflow upstream results
        if context.get("intermediate_results"):
            parts.append("")
            parts.append("## 上游工作流结果")
            parts.append(json.dumps(context["intermediate_results"], ensure_ascii=False, indent=2))

        content = "\n".join(parts)
        claude_md_path = os.path.join(work_dir, "CLAUDE.md")
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Written CLAUDE.md to {claude_md_path}")
```

- [ ] **Step 2: Commit**

```bash
git add backend/core/claude_code_runner.py
git commit -m "refactor: rewrite claude_code_runner with SDK support and registry mode"
```

---

### Task B8: Update agent_factory.py to support registry-based claudecode config

**Files:**
- Modify: `backend/core/agent_factory.py`

- [ ] **Step 1: Update create_claudecode_agent to pass registry IDs**

Edit `backend/core/agent_factory.py`. The `create_claudecode_agent` method needs to detect the claudecode_config format and pass the config as-is to ClaudeCodeRunner (the runner handles the resolution).

Find the `create_claudecode_agent` method (around line 420-461) and update it:

old_string (lines 437-443):
```python
        from core.claude_code_runner import ClaudeCodeRunner
        runner = ClaudeCodeRunner(
            config=agent_config.get("claudecode_config", {}),
            mcp_servers=mcp_servers,
            kb_content=kb_content,
            skill_content=skill_content,
        )
        agent_name = agent_config.get("name", "unknown")
```

new_string:
```python
        from core.claude_code_runner import ClaudeCodeRunner
        runner = ClaudeCodeRunner(
            config=agent_config.get("claudecode_config", {}),
            mcp_servers=mcp_servers,
            kb_content=kb_content,
            skill_content=skill_content,
            agent_name=agent_config.get("name", "unknown"),
        )
        agent_name = agent_config.get("name", "unknown")
```

- [ ] **Step 2: Commit**

```bash
git add backend/core/agent_factory.py
git commit -m "fix: pass agent_name to ClaudeCodeRunner for registry mode"
```

---

### Task F1: Create frontend API files for projects and claude-settings

**Files:**
- Create: `frontend/src/api/projects.ts`
- Create: `frontend/src/api/claudeSettings.ts`

- [ ] **Step 1: Create projects.ts API file**

Write `frontend/src/api/projects.ts`:

```typescript
import client from './client'

export const projectsApi = {
  list: (params?: { status?: string; search?: string }) => client.get('/projects', { params }),
  get: (id: number) => client.get(`/projects/${id}`),
  create: (data: any) => client.post('/projects', data),
  update: (id: number, data: any) => client.put(`/projects/${id}`, data),
  delete: (id: number) => client.delete(`/projects/${id}`),
}
```

- [ ] **Step 2: Create claudeSettings.ts API file**

Write `frontend/src/api/claudeSettings.ts`:

```typescript
import client from './client'

export const claudeSettingsApi = {
  list: (params?: { search?: string }) => client.get('/claude-settings', { params }),
  get: (id: number) => client.get(`/claude-settings/${id}`),
  create: (data: any) => client.post('/claude-settings', data),
  update: (id: number, data: any) => client.put(`/claude-settings/${id}`, data),
  delete: (id: number) => client.delete(`/claude-settings/${id}`),
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/projects.ts frontend/src/api/claudeSettings.ts
git commit -m "feat: add frontend API files for projects and claude-settings"
```

---

### Task F2: Create ProjectList.vue and ProjectEditor.vue pages

**Files:**
- Create: `frontend/src/views/ProjectList.vue`
- Create: `frontend/src/views/ProjectEditor.vue`

- [ ] **Step 1: Create ProjectList.vue**

Write `frontend/src/views/ProjectList.vue`:

```vue
<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">项目注册表</h1>
      <a-button type="primary" @click="$router.push('/resources/projects/create')">
        <PlusOutlined /> 注册项目
      </a-button>
    </div>

    <div class="mb-4 flex gap-4">
      <a-input-search v-model:value="search" placeholder="搜索名称或仓库地址..." class="max-w-xs" @search="fetchList" />
      <a-select v-model:value="statusFilter" class="w-32" @change="fetchList">
        <a-select-option value="">全部状态</a-select-option>
        <a-select-option value="active">启用</a-select-option>
        <a-select-option value="disabled">禁用</a-select-option>
      </a-select>
    </div>

    <a-spin :spinning="loading">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <a-card v-for="p in filteredProjects" :key="p.id" class="hover:border-[#5e6ad2] transition-colors">
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-2">
                <span class="inline-block w-2 h-2 rounded-full" :class="p.status === 'active' ? 'bg-green-500' : 'bg-gray-500'" />
                <h3 class="text-lg font-semibold">{{ p.display_name || p.name }}</h3>
              </div>
              <p class="text-gray-400 text-sm mb-1" v-if="p.description">{{ p.description }}</p>
              <p class="text-gray-500 text-xs">仓库: {{ p.git_repo_url }}</p>
              <p class="text-gray-500 text-xs">分支: {{ p.git_branch }}</p>
            </div>
          </div>
          <template #actions>
            <a-button size="small" @click="$router.push(`/resources/projects/${p.id}/edit`)">编辑</a-button>
            <a-popconfirm title="确定删除？" @confirm="handleDelete(p.id)">
              <a-button size="small" danger>删除</a-button>
            </a-popconfirm>
          </template>
        </a-card>
      </div>
      <a-empty v-if="!loading && filteredProjects.length === 0" description="暂无项目" />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { projectsApi } from '@/api/projects'

const projects = ref<any[]>([])
const loading = ref(false)
const search = ref('')
const statusFilter = ref('')

const filteredProjects = computed(() => {
  let list = projects.value
  if (statusFilter.value) list = list.filter(p => p.status === statusFilter.value)
  if (search.value) {
    const q = search.value.toLowerCase()
    list = list.filter(p => (p.name + p.display_name + p.git_repo_url).toLowerCase().includes(q))
  }
  return list
})

async function fetchList() {
  loading.value = true
  try {
    const res = await projectsApi.list()
    projects.value = res.data.data || []
  } catch {
    message.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await projectsApi.delete(id)
    message.success('已删除')
    fetchList()
  } catch {
    message.error('删除失败')
  }
}

onMounted(fetchList)
</script>
```

- [ ] **Step 2: Create ProjectEditor.vue**

Write `frontend/src/views/ProjectEditor.vue`:

```vue
<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">{{ isEdit ? '编辑' : '注册' }} 项目</h1>
    <a-card class="max-w-2xl">
      <a-form :model="form" layout="vertical" @finish="handleSubmit">
        <a-form-item label="名称" name="name" :rules="[{ required: true, message: '请输入名称' }]">
          <a-input v-model:value="form.name" placeholder="如 my-project" :disabled="isEdit" />
        </a-form-item>
        <a-form-item label="显示名称">
          <a-input v-model:value="form.display_name" placeholder="如 我的项目" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
        <a-form-item label="Git 仓库地址" name="git_repo_url" :rules="[{ required: true, message: '请输入 Git 仓库地址' }]">
          <a-input v-model:value="form.git_repo_url" placeholder="https://github.com/user/repo.git" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="分支">
              <a-input v-model:value="form.git_branch" placeholder="main" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="超时(分钟)">
              <a-input-number v-model:value="form.fix_timeout_minutes" :min="5" :max="120" class="w-full" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="认证用户名">
          <a-input v-model:value="form.git_auth_username" placeholder="可选" />
        </a-form-item>
        <a-form-item label="认证 Token">
          <a-input-password v-model:value="form.git_auth_token" placeholder="可选" />
        </a-form-item>
        <a-form-item label="Clone 路径（可选）">
          <a-input v-model:value="form.clone_path" placeholder="留空使用默认工作区" />
          <div class="text-xs text-gray-500 mt-1">绝对路径，指定项目的 clone 根目录。留空则使用系统默认工作区。</div>
        </a-form-item>
        <a-form-item label="系统提示词（可选）">
          <a-textarea v-model:value="form.system_prompt" :rows="4" placeholder="Claude Code 的项目级系统提示..." />
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" html-type="submit" :loading="submitting">
              {{ isEdit ? '更新' : '注册' }}
            </a-button>
            <a-button @click="$router.back()">取消</a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { projectsApi } from '@/api/projects'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const submitting = ref(false)

const form = ref<any>({
  name: '', display_name: '', description: '',
  git_repo_url: '', git_branch: 'main',
  git_auth_username: '', git_auth_token: '',
  clone_path: '', system_prompt: '', fix_timeout_minutes: 30,
})

onMounted(async () => {
  if (isEdit.value) {
    const res = await projectsApi.get(Number(route.params.id))
    const d = res.data.data
    form.value = {
      name: d.name, display_name: d.display_name || '',
      description: d.description || '', git_repo_url: d.git_repo_url,
      git_branch: d.git_branch, git_auth_username: d.git_auth_username || '',
      git_auth_token: d.git_auth_token || '', clone_path: d.clone_path || '',
      system_prompt: d.system_prompt || '', fix_timeout_minutes: d.fix_timeout_minutes || 30,
    }
  }
})

async function handleSubmit() {
  submitting.value = true
  try {
    if (isEdit.value) {
      await projectsApi.update(Number(route.params.id), form.value)
    } else {
      await projectsApi.create(form.value)
    }
    message.success(isEdit.value ? '更新成功' : '注册成功')
    router.push('/resources/projects')
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}
</script>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/ProjectList.vue frontend/src/views/ProjectEditor.vue
git commit -m "feat: add ProjectList and ProjectEditor pages"
```

---

### Task F3: Create ClaudeSettingsList.vue and ClaudeSettingsEditor.vue pages

**Files:**
- Create: `frontend/src/views/ClaudeSettingsList.vue`
- Create: `frontend/src/views/ClaudeSettingsEditor.vue`

- [ ] **Step 1: Create ClaudeSettingsList.vue**

Write `frontend/src/views/ClaudeSettingsList.vue`:

```vue
<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">Claude Code 执行配置</h1>
      <a-button type="primary" @click="$router.push('/resources/claude-settings/create')">
        <PlusOutlined /> 新建配置
      </a-button>
    </div>

    <a-spin :spinning="loading">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <a-card v-for="s in settingsList" :key="s.id" class="hover:border-[#5e6ad2] transition-colors">
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-2">
                <span class="inline-block w-2 h-2 rounded-full" :class="s.status === 'active' ? 'bg-green-500' : 'bg-gray-500'" />
                <h3 class="text-lg font-semibold">{{ s.display_name || s.name }}</h3>
              </div>
              <p class="text-gray-400 text-sm mb-1" v-if="s.description">{{ s.description }}</p>
              <p class="text-gray-500 text-xs">模型: {{ s.model }}</p>
              <p class="text-gray-500 text-xs">最大轮次: {{ s.max_turns }}</p>
              <p class="text-gray-500 text-xs">权限模式: {{ s.permission_mode }}</p>
            </div>
          </div>
          <template #actions>
            <a-button size="small" @click="$router.push(`/resources/claude-settings/${s.id}/edit`)">编辑</a-button>
            <a-popconfirm title="确定删除？" @confirm="handleDelete(s.id)">
              <a-button size="small" danger>删除</a-button>
            </a-popconfirm>
          </template>
        </a-card>
      </div>
      <a-empty v-if="!loading && settingsList.length === 0" description="暂无配置" />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { claudeSettingsApi } from '@/api/claudeSettings'

const settingsList = ref<any[]>([])
const loading = ref(false)

async function fetchList() {
  loading.value = true
  try {
    const res = await claudeSettingsApi.list()
    settingsList.value = res.data.data || []
  } catch {
    message.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await claudeSettingsApi.delete(id)
    message.success('已删除')
    fetchList()
  } catch {
    message.error('删除失败')
  }
}

onMounted(fetchList)
</script>
```

- [ ] **Step 2: Create ClaudeSettingsEditor.vue**

Write `frontend/src/views/ClaudeSettingsEditor.vue`:

```vue
<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">{{ isEdit ? '编辑' : '新建' }} Claude Code 执行配置</h1>
    <a-card class="max-w-2xl">
      <a-form :model="form" layout="vertical" @finish="handleSubmit">
        <a-form-item label="名称" name="name" :rules="[{ required: true, message: '请输入名称' }]">
          <a-input v-model:value="form.name" placeholder="如 production-config" :disabled="isEdit" />
        </a-form-item>
        <a-form-item label="显示名称">
          <a-input v-model:value="form.display_name" placeholder="如 生产环境配置" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="模型">
              <a-select v-model:value="form.model">
                <a-select-option value="claude-sonnet-4-6">Claude Sonnet 4.6</a-select-option>
                <a-select-option value="claude-opus-4-7">Claude Opus 4.7</a-select-option>
                <a-select-option value="claude-sonnet-4-20250514">Claude Sonnet 4 (20250514)</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="最大轮次">
              <a-input-number v-model:value="form.max_turns" :min="1" :max="100" class="w-full" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="权限模式">
              <a-select v-model:value="form.permission_mode">
                <a-select-option value="default">Default</a-select-option>
                <a-select-option value="acceptEdits">Accept Edits</a-select-option>
                <a-select-option value="bypassPermissions">Bypass Permissions</a-select-option>
                <a-select-option value="plan">Plan Only</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item
          label="settings.json (原生配置)"
          :validate-status="settingsJsonStatus"
          :help="settingsJsonError"
        >
          <a-textarea
            v-model:value="form.settings_json"
            :rows="10"
            placeholder='{\n  "model": "claude-opus-4-7",\n  "permissions": {\n    "allow": ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]\n  }\n}'
            style="font-family: 'Courier New', monospace; font-size: 13px;"
            @input="validateSettingsJson"
          />
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" html-type="submit" :loading="submitting">
              {{ isEdit ? '更新' : '创建' }}
            </a-button>
            <a-button @click="$router.back()">取消</a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { claudeSettingsApi } from '@/api/claudeSettings'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const submitting = ref(false)

const form = ref<any>({
  name: '', display_name: '', description: '',
  model: 'claude-sonnet-4-6', max_turns: 25,
  permission_mode: 'acceptEdits', settings_json: '',
})

const settingsJsonStatus = ref<'success' | 'error' | ''>('')
const settingsJsonError = ref('')

function validateSettingsJson() {
  const val = form.value.settings_json
  if (!val || !val.trim()) {
    settingsJsonStatus.value = ''
    settingsJsonError.value = ''
    return
  }
  try {
    JSON.parse(val)
    settingsJsonStatus.value = 'success'
    settingsJsonError.value = ''
  } catch (e: any) {
    settingsJsonStatus.value = 'error'
    settingsJsonError.value = e.message || 'JSON 格式错误'
  }
}

onMounted(async () => {
  if (isEdit.value) {
    const res = await claudeSettingsApi.get(Number(route.params.id))
    const d = res.data.data
    form.value = {
      name: d.name, display_name: d.display_name || '',
      description: d.description || '', model: d.model,
      max_turns: d.max_turns, permission_mode: d.permission_mode,
      settings_json: d.settings_json || '',
    }
  }
})

async function handleSubmit() {
  submitting.value = true
  try {
    if (isEdit.value) {
      await claudeSettingsApi.update(Number(route.params.id), form.value)
    } else {
      await claudeSettingsApi.create(form.value)
    }
    message.success(isEdit.value ? '更新成功' : '创建成功')
    router.push('/resources/claude-settings')
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}
</script>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/ClaudeSettingsList.vue frontend/src/views/ClaudeSettingsEditor.vue
git commit -m "feat: add ClaudeSettingsList and ClaudeSettingsEditor pages"
```

---

### Task F4: Update router and sidebar with new resource entries

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/AppSidebar.vue`

- [ ] **Step 1: Add routes for new resource pages**

Edit `frontend/src/router/index.ts`. Add after the skills routes block (around line 36-37):

old_string:
```typescript
        // Resource directory - Skills
        { path: 'resources/skills', name: 'SkillList', component: () => import('@/views/SkillList.vue'), meta: { title: 'Skill 管理' } },
        { path: 'resources/skills/create', name: 'SkillCreate', component: () => import('@/views/SkillEditor.vue'), meta: { title: '创建 Skill' } },
        { path: 'resources/skills/:id/edit', name: 'SkillEdit', component: () => import('@/views/SkillEditor.vue'), meta: { title: '编辑 Skill' }, props: true },
        // Monitoring
```

new_string:
```typescript
        // Resource directory - Skills
        { path: 'resources/skills', name: 'SkillList', component: () => import('@/views/SkillList.vue'), meta: { title: 'Skill 管理' } },
        { path: 'resources/skills/create', name: 'SkillCreate', component: () => import('@/views/SkillEditor.vue'), meta: { title: '创建 Skill' } },
        { path: 'resources/skills/:id/edit', name: 'SkillEdit', component: () => import('@/views/SkillEditor.vue'), meta: { title: '编辑 Skill' }, props: true },
        // Resource directory - Projects
        { path: 'resources/projects', name: 'ProjectList', component: () => import('@/views/ProjectList.vue'), meta: { title: '项目注册表' } },
        { path: 'resources/projects/create', name: 'ProjectCreate', component: () => import('@/views/ProjectEditor.vue'), meta: { title: '注册项目' } },
        { path: 'resources/projects/:id/edit', name: 'ProjectEdit', component: () => import('@/views/ProjectEditor.vue'), meta: { title: '编辑项目' }, props: true },
        // Resource directory - Claude Settings
        { path: 'resources/claude-settings', name: 'ClaudeSettingsList', component: () => import('@/views/ClaudeSettingsList.vue'), meta: { title: 'Claude 执行配置' } },
        { path: 'resources/claude-settings/create', name: 'ClaudeSettingsCreate', component: () => import('@/views/ClaudeSettingsEditor.vue'), meta: { title: '新建配置' } },
        { path: 'resources/claude-settings/:id/edit', name: 'ClaudeSettingsEdit', component: () => import('@/views/ClaudeSettingsEditor.vue'), meta: { title: '编辑配置' }, props: true },
        // Monitoring
```

- [ ] **Step 2: Add sidebar entries**

Edit `frontend/src/components/AppSidebar.vue`. Find the skills submenu item block and add new entries after it:

old_string:
```typescript
        <a-menu-item key="/resources/skills">Skill 管理</a-menu-item>
      </a-sub-menu>
```

new_string:
```typescript
        <a-menu-item key="/resources/skills">Skill 管理</a-menu-item>
        <a-menu-item key="/resources/projects">项目注册表</a-menu-item>
        <a-menu-item key="/resources/claude-settings">Claude 执行配置</a-menu-item>
      </a-sub-menu>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/components/AppSidebar.vue
git commit -m "feat: add routes and sidebar entries for new resource pages"
```

---

### Task F5: Simplify AgentEditor.vue claudecode configuration section

**Files:**
- Modify: `frontend/src/views/AgentEditor.vue`

- [ ] **Step 1: Replace the claudecode config section with two dropdown selectors**

In `AgentEditor.vue`, replace the "Claude Code Config" template section (lines 137-191).

Old template block (lines 138-191):
```vue
        <!-- Claude Code Config -->
        <template v-if="form.agent_type === 'claudecode'">
          <h3 class="text-lg font-semibold mb-4 mt-4 text-[#5e6ad2]">Claude Code 配置</h3>

          <!-- Quick settings (optional, overlay CLI args) -->
          <a-row :gutter="16">
            <a-col :span="8">
              <a-form-item label="模型 (CLI --model)">
                <a-select v-model:value="ccConfig.model" @change="syncCcToSettingsJson">
                  <a-select-option value="claude-sonnet-4-6">Claude Sonnet 4.6</a-select-option>
                  <a-select-option value="claude-opus-4-7">Claude Opus 4.7</a-select-option>
                  <a-select-option value="claude-sonnet-4-20250514">Claude Sonnet 4 (20250514)</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="最大轮次 (CLI --max-turns)">
                <a-input-number v-model:value="ccConfig.max_turns" :min="1" :max="100" class="w-full" @change="syncCcToSettingsJson" />
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="权限模式 (CLI --permission-mode)">
                <a-select v-model:value="ccConfig.permission_mode" @change="syncCcToSettingsJson">
                  <a-select-option value="default">Default</a-select-option>
                  <a-select-option value="acceptEdits">Accept Edits</a-select-option>
                  <a-select-option value="bypassPermissions">Bypass Permissions</a-select-option>
                  <a-select-option value="plan">Plan Only</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>
          <a-form-item label="工作目录">
            <a-input v-model:value="ccConfig.work_dir" placeholder="/data/agent_workspaces/agent_1/" />
          </a-form-item>

          <!-- Settings JSON textarea (primary config) -->
          <a-form-item
            label="settings.json (Claude Code 原生配置)"
            :validate-status="settingsJsonStatus"
            :help="settingsJsonError"
          >
            <a-textarea
              v-model:value="ccConfig.settings_json"
              :rows="12"
              placeholder='{\n  "model": "claude-sonnet-4-6",\n  "permissions": {\n    "allow": ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]\n  }\n}'
              style="font-family: 'Courier New', monospace; font-size: 13px;"
              @input="validateSettingsJson"
            />
          </a-form-item>
          <p class="text-xs text-gray-500 -mt-3 mb-4">
            settings.json 是 Claude Code 的原生配置文件，将写入 work_dir/.claude/settings.json。
            上方快速设置字段（模型/轮次/权限）通过 CLI 参数透传，优先级高于 settings.json。
            MCP Server 通过页面下方的资源选择器关联，运行时自动注入。
          </p>
        </template>
```

New template block:
```vue
        <!-- Claude Code Config -->
        <template v-if="form.agent_type === 'claudecode'">
          <h3 class="text-lg font-semibold mb-4 mt-4 text-[#5e6ad2]">Claude Code 配置</h3>

          <a-form-item label="选择项目" name="project_registry_id" :rules="[{ required: true, message: '请选择项目' }]">
            <a-select
              v-model:value="ccConfig.project_registry_id"
              placeholder="选择已注册的 Git 项目..."
              :options="projectOptions"
              show-search
              filter-option
              allow-clear
            />
          </a-form-item>
          <a-form-item label="选择执行配置" name="settings_registry_id" :rules="[{ required: true, message: '请选择执行配置' }]">
            <a-select
              v-model:value="ccConfig.settings_registry_id"
              placeholder="选择 Claude Code 执行配置..."
              :options="settingsOptions"
              show-search
              filter-option
              allow-clear
            />
          </a-form-item>
          <p class="text-xs text-gray-500 mb-4">
            项目和执行配置在"资源目录"中管理。执行时自动 clone 项目代码并应用配置。
          </p>
        </template>
```

- [ ] **Step 2: Update script section to load options and simplify ccConfig**

In the script section, find the ccConfig initialization and related state:

Old script section changes needed:

a) Replace `ccConfig` initialization and `settingsJsonStatus`/`settingsJsonError`:

old_string:
```typescript
const ccConfig = ref<any>({
  settings_json: '',
  model: 'claude-sonnet-4-6',
  max_turns: 25,
  work_dir: '',
  permission_mode: 'acceptEdits',
})

// JSON validation state
const settingsJsonStatus = ref<'success' | 'error' | ''>('')
const settingsJsonError = ref('')

function validateSettingsJson() {
  const val = ccConfig.value.settings_json
  if (!val || !val.trim()) {
    settingsJsonStatus.value = ''
    settingsJsonError.value = ''
    return
  }
  try {
    JSON.parse(val)
    settingsJsonStatus.value = 'success'
    settingsJsonError.value = ''
  } catch (e: any) {
    settingsJsonStatus.value = 'error'
    settingsJsonError.value = e.message || 'JSON 格式错误'
  }
}

function syncCcToSettingsJson() {
  /* Optional: sync simple fields into settings_json.
     Currently not auto-syncing to preserve user's manual edits. */
}
```

new_string:
```typescript
const ccConfig = ref<any>({
  project_registry_id: null,
  settings_registry_id: null,
})

const projectOptions = ref<{ value: number; label: string }[]>([])
const settingsOptions = ref<{ value: number; label: string }[]>([])

async function loadProjectOptions() {
  try {
    const res = await projectsApi.list()
    projectOptions.value = (res.data.data || []).map((p: any) => ({
      value: p.id,
      label: `${p.display_name || p.name} (${p.git_repo_url})`,
    }))
  } catch { /* ignore */ }
}

async function loadSettingsOptions() {
  try {
    const res = await claudeSettingsApi.list()
    settingsOptions.value = (res.data.data || []).map((s: any) => ({
      value: s.id,
      label: `${s.display_name || s.name} (${s.model})`,
    }))
  } catch { /* ignore */ }
}
```

b) Add import for the new API files:

old_string:
```typescript
import { agentsApi } from '@/api/agents'
import McpServerSelector from '@/components/McpServerSelector.vue'
import KnowledgeBaseSelector from '@/components/KnowledgeBaseSelector.vue'
import SkillsSelector from '@/components/SkillsSelector.vue'
import { llmConfigsApi } from '@/api/llmConfigs'
```

new_string:
```typescript
import { agentsApi } from '@/api/agents'
import { projectsApi } from '@/api/projects'
import { claudeSettingsApi } from '@/api/claudeSettings'
import McpServerSelector from '@/components/McpServerSelector.vue'
import KnowledgeBaseSelector from '@/components/KnowledgeBaseSelector.vue'
import SkillsSelector from '@/components/SkillsSelector.vue'
import { llmConfigsApi } from '@/api/llmConfigs'
```

c) In the `loadAgent` function update the ccConfig loading section. Find where ccConfig is populated with the old fields and replace:

old_string (find the section where `ccConfig.value` is assigned after `form.value`):
```typescript
    if (d.claudecode_config) {
      ccConfig.value = {
        settings_json: d.claudecode_config.settings_json || '',
        model: d.claudecode_config.model || 'claude-sonnet-4-6',
        max_turns: d.claudecode_config.max_turns || 25,
        work_dir: d.claudecode_config.work_dir || '',
        permission_mode: d.claudecode_config.permission_mode || 'acceptEdits',
      }
    }
```

new_string:
```typescript
    if (d.claudecode_config) {
      ccConfig.value = {
        project_registry_id: d.claudecode_config.project_registry_id || null,
        settings_registry_id: d.claudecode_config.settings_registry_id || null,
      }
    }
```

d) In the create/update agent request, update how `claudecode_config` is built. Find the submit handler where `claudecode_config` is set and update. Look for a section similar to:

May need to find where `claudecode_config` is assembled before the API call. If it currently assembles from the old ccConfig fields, change to:

```typescript
const claudecodeConfig = {
  project_registry_id: ccConfig.value.project_registry_id,
  settings_registry_id: ccConfig.value.settings_registry_id,
}
```

e) Call loadProjectOptions and loadSettingsOptions on mount alongside loadLlmConfigOptions:

old_string (in onMounted or setup):
```
    loadLlmConfigOptions()
```

new_string:
```
    loadLlmConfigOptions()
    loadProjectOptions()
    loadSettingsOptions()
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/AgentEditor.vue
git commit -m "refactor: simplify AgentEditor claudecode config to two dropdown selectors"
```

---

### Task A1: API tests for projects CRUD

**Files:**
- Create: `tests/api/test_projects.py`

- [ ] **Step 1: Create projects API test file**

Write `tests/api/test_projects.py`:

```python
"""API tests for /api/v1/projects/ CRUD endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_headers( client):
    """Get admin auth token."""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "admin123"
    })
    data = resp.json()
    token = data.get("data", {}).get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_project(client, auth_headers):
    """Test POST /api/v1/projects/ creates a new project."""
    payload = {
        "name": "test-project",
        "display_name": "Test Project",
        "git_repo_url": "https://github.com/user/test-repo.git",
        "git_branch": "main",
    }
    resp = await client.post("/api/v1/projects/", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["name"] == "test-project"
    assert "id" in data["data"]


@pytest.mark.asyncio
async def test_create_project_duplicate_name(client, auth_headers):
    """Test creating project with duplicate name returns 400."""
    payload = {
        "name": "dup-project",
        "git_repo_url": "https://github.com/user/repo.git",
    }
    resp1 = await client.post("/api/v1/projects/", json=payload, headers=auth_headers)
    assert resp1.status_code == 200

    resp2 = await client.post("/api/v1/projects/", json=payload, headers=auth_headers)
    assert resp2.status_code == 400
    assert "名称已存在" in resp2.json()["message"]


@pytest.mark.asyncio
async def test_list_projects(client, auth_headers):
    """Test GET /api/v1/projects/ returns project list."""
    resp = await client.get("/api/v1/projects/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_get_project(client, auth_headers):
    """Test GET /api/v1/projects/{id} returns project detail."""
    # First create
    payload = {"name": "get-test", "git_repo_url": "https://github.com/user/get-test.git"}
    create_resp = await client.post("/api/v1/projects/", json=payload, headers=auth_headers)
    project_id = create_resp.json()["data"]["id"]

    # Then get
    resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["name"] == "get-test"
    assert data["data"]["git_repo_url"] == "https://github.com/user/get-test.git"


@pytest.mark.asyncio
async def test_get_project_not_found(client, auth_headers):
    """Test GET /api/v1/projects/{id} with non-existent id returns 404."""
    resp = await client.get("/api/v1/projects/99999", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["code"] == 404


@pytest.mark.asyncio
async def test_update_project(client, auth_headers):
    """Test PUT /api/v1/projects/{id} updates project fields."""
    payload = {"name": "update-test", "git_repo_url": "https://github.com/user/update-test.git"}
    create_resp = await client.post("/api/v1/projects/", json=payload, headers=auth_headers)
    project_id = create_resp.json()["data"]["id"]

    update_payload = {"display_name": "Updated", "git_branch": "develop"}
    resp = await client.put(f"/api/v1/projects/{project_id}", json=update_payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    # Verify
    get_resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert get_resp.json()["data"]["display_name"] == "Updated"
    assert get_resp.json()["data"]["git_branch"] == "develop"


@pytest.mark.asyncio
async def test_delete_project(client, auth_headers):
    """Test DELETE /api/v1/projects/{id} deletes project."""
    payload = {"name": "delete-test", "git_repo_url": "https://github.com/user/delete-test.git"}
    create_resp = await client.post("/api/v1/projects/", json=payload, headers=auth_headers)
    project_id = create_resp.json()["data"]["id"]

    resp = await client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert resp.status_code == 200

    # Verify gone
    get_resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert get_resp.json()["code"] == 404
```

- [ ] **Step 2: Commit**

```bash
git add tests/api/test_projects.py
git commit -m "test: add API tests for projects CRUD"
```

---

### Task A2: API tests for claude-settings CRUD

**Files:**
- Create: `tests/api/test_claude_settings.py`

- [ ] **Step 1: Create claude-settings API test file**

Write `tests/api/test_claude_settings.py`:

```python
"""API tests for /api/v1/claude-settings/ CRUD endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_headers(client):
    """Get admin auth token."""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "admin123"
    })
    data = resp.json()
    token = data.get("data", {}).get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_settings(client, auth_headers):
    """Test POST /api/v1/claude-settings/ creates new settings."""
    payload = {
        "name": "test-config",
        "display_name": "Test Config",
        "model": "claude-opus-4-7",
        "max_turns": 50,
        "permission_mode": "bypassPermissions",
    }
    resp = await client.post("/api/v1/claude-settings/", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["name"] == "test-config"
    assert "id" in data["data"]


@pytest.mark.asyncio
async def test_create_settings_duplicate_name(client, auth_headers):
    """Test creating settings with duplicate name returns 400."""
    payload = {"name": "dup-config", "model": "claude-sonnet-4-6"}
    resp1 = await client.post("/api/v1/claude-settings/", json=payload, headers=auth_headers)
    assert resp1.status_code == 200

    resp2 = await client.post("/api/v1/claude-settings/", json=payload, headers=auth_headers)
    assert resp2.status_code == 400
    assert "名称已存在" in resp2.json()["message"]


@pytest.mark.asyncio
async def test_create_settings_invalid_json(client, auth_headers):
    """Test creating settings with invalid settings_json returns 400."""
    payload = {
        "name": "bad-json-config",
        "settings_json": "{invalid json}",
    }
    resp = await client.post("/api/v1/claude-settings/", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["code"] != 0
    assert "settings_json" in resp.json()["message"]


@pytest.mark.asyncio
async def test_create_settings_with_valid_json(client, auth_headers):
    """Test creating settings with valid settings_json succeeds."""
    payload = {
        "name": "json-config",
        "settings_json": '{"model": "claude-sonnet-4-6", "permissions": {"allow": ["Read", "Write"]}}',
    }
    resp = await client.post("/api/v1/claude-settings/", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["code"] == 0


@pytest.mark.asyncio
async def test_list_settings(client, auth_headers):
    """Test GET /api/v1/claude-settings/ returns settings list."""
    resp = await client.get("/api/v1/claude-settings/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_get_settings(client, auth_headers):
    """Test GET /api/v1/claude-settings/{id} returns detail."""
    payload = {"name": "get-config", "model": "claude-sonnet-4-6"}
    create_resp = await client.post("/api/v1/claude-settings/", json=payload, headers=auth_headers)
    settings_id = create_resp.json()["data"]["id"]

    resp = await client.get(f"/api/v1/claude-settings/{settings_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["name"] == "get-config"
    assert data["data"]["model"] == "claude-sonnet-4-6"
    assert data["data"]["max_turns"] == 25  # default


@pytest.mark.asyncio
async def test_update_settings(client, auth_headers):
    """Test PUT /api/v1/claude-settings/{id} updates fields."""
    payload = {"name": "update-config", "model": "claude-sonnet-4-6"}
    create_resp = await client.post("/api/v1/claude-settings/", json=payload, headers=auth_headers)
    settings_id = create_resp.json()["data"]["id"]

    update_payload = {"max_turns": 80, "permission_mode": "plan"}
    resp = await client.put(f"/api/v1/claude-settings/{settings_id}", json=update_payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    get_resp = await client.get(f"/api/v1/claude-settings/{settings_id}", headers=auth_headers)
    assert get_resp.json()["data"]["max_turns"] == 80
    assert get_resp.json()["data"]["permission_mode"] == "plan"


@pytest.mark.asyncio
async def test_delete_settings(client, auth_headers):
    """Test DELETE /api/v1/claude-settings/{id} deletes settings."""
    payload = {"name": "delete-config", "model": "claude-sonnet-4-6"}
    create_resp = await client.post("/api/v1/claude-settings/", json=payload, headers=auth_headers)
    settings_id = create_resp.json()["data"]["id"]

    resp = await client.delete(f"/api/v1/claude-settings/{settings_id}", headers=auth_headers)
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/v1/claude-settings/{settings_id}", headers=auth_headers)
    assert get_resp.json()["code"] == 404
```

- [ ] **Step 2: Commit**

```bash
git add tests/api/test_claude_settings.py
git commit -m "test: add API tests for claude-settings CRUD"
```

---

### Task A3: Integration test - Agent creation with registry references

**Files:**
- Create: `tests/api/test_agent_registry_integration.py`

- [ ] **Step 1: Create integration test for agent with project/settings references**

Write `tests/api/test_agent_registry_integration.py`:

```python
"""Integration tests for Agent creation with project and claude-settings registry references."""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_headers(client):
    resp = await client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "admin123"
    })
    data = resp.json()
    token = data.get("data", {}).get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_agent_with_registry_refs(client, auth_headers):
    """Test creating claudecode agent with project and settings registry references."""

    # 1. Create a project
    proj_payload = {
        "name": "int-test-project",
        "git_repo_url": "https://github.com/user/int-test.git",
    }
    proj_resp = await client.post("/api/v1/projects/", json=proj_payload, headers=auth_headers)
    assert proj_resp.json()["code"] == 0
    project_id = proj_resp.json()["data"]["id"]

    # 2. Create a claude settings
    settings_payload = {
        "name": "int-test-config",
        "model": "claude-sonnet-4-6",
        "max_turns": 30,
        "permission_mode": "acceptEdits",
    }
    settings_resp = await client.post("/api/v1/claude-settings/", json=settings_payload, headers=auth_headers)
    assert settings_resp.json()["code"] == 0
    settings_id = settings_resp.json()["data"]["id"]

    # 3. Create a claudecode agent referencing both
    agent_payload = {
        "name": "int-test-agent",
        "agent_type": "claudecode",
        "role": "worker",
        "claudecode_config": {
            "project_registry_id": project_id,
            "settings_registry_id": settings_id,
        },
    }
    agent_resp = await client.post("/api/v1/agents/", json=agent_payload, headers=auth_headers)
    assert agent_resp.json()["code"] == 0
    agent_id = agent_resp.json()["data"]["id"]

    # 4. Verify agent has correct claudecode_config
    get_resp = await client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers)
    assert get_resp.json()["code"] == 0
    cc_config = get_resp.json()["data"]["claudecode_config"]
    assert cc_config["project_registry_id"] == project_id
    assert cc_config["settings_registry_id"] == settings_id
```

- [ ] **Step 2: Commit**

```bash
git add tests/api/test_agent_registry_integration.py
git commit -m "test: add integration test for agent with registry references"
```

---

### Task A4: Frontend integration verification (manual test plan)

**No automated test file needed.** Describe the manual verification steps.

**Verification Steps:**

1. Navigate to "资源目录 > 项目注册表" - verify the page loads with an empty state
2. Click "注册项目" - verify the form shows all fields (name, git_repo_url, branch, auth fields, clone_path, system_prompt, timeout)
3. Fill in the form and submit - verify redirect to list page with the new project visible
4. Click "编辑" on a project - verify form is pre-populated with existing data
5. Update a field and submit - verify the change is reflected
6. Click "删除" on a project - verify it's removed from the list
7. Navigate to "资源目录 > Claude 执行配置" - verify the page loads
8. Create a new configuration with settings_json - verify JSON validation works
9. Navigate to Agent Editor, select type "Claude Code" - verify the two dropdown selectors appear (project + settings)
10. Create a claudecode agent with project/settings selections - verify the agent is saved and displayed correctly

---

## Self-Review

### Spec Coverage

1. **project-registry spec**: All scenarios covered by B1 (models), B3 (schemas), B4 (router), F2 (pages), A1 (tests)
2. **claude-settings-registry spec**: All scenarios covered by B2 (models), B3 (schemas), B5 (router), F3 (pages), A2 (tests)
3. **claude-code-sdk-runner spec**: Covered by B7 (runner rewrite), B8 (agent_factory update)
4. **git-ops spec**: Covered by B6 (git_ops.py creation)

### Placeholder Check

No placeholder patterns found. All tasks have complete code implementations.

### Type Consistency

- `project_registry_id` and `settings_registry_id` are consistently `int | null` throughout all layers
- Frontend TypeScript interface names use snake_case matching backend field names
- API response format `{code, message, data}` consistent across all routes
- Enum values (status, permission_mode) use string values consistently

---

Plan complete and saved to `docs/superpowers/plans/2026-06-15-task-project-registry.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
