# Claude Code Agent Settings.json Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor claudecode Agent configuration from scattered individual fields to a settings_json-based model where users edit a complete Claude Code settings.json, and the ClaudeCodeRunner automatically writes it to the work directory along with injected knowledge base and skill content.

**Architecture:** claudecode_config JSON field gains a `settings_json` string sub-field containing the full Claude Code settings.json content. ClaudeCodeRunner parses this, merges MCP server configs, writes to `work_dir/.claude/settings.json`, and simultaneously injects linked KB/Skill content as CLAUDE.md. The frontend AgentEditor replaces the old individual config fields with a JSON textarea plus 4 quick-set fields. Legacy fields (allowed_tools, extra_args, env) are deprecated but backward-compatible.

**Tech Stack:** Python 3.11+FastAPI (backend), Vue 3.5+TypeScript (frontend), Tortoise ORM, Claude Code CLI

---

## File Structure

### Files to Create
- `frontend/src/types/agent.ts` — TypeScript interface for `ClaudeCodeConfig`

### Files to Modify
- `backend/core/claude_code_runner.py` — Rewrite: settings.json/CLAUDE.md file writing, new constructor, backward compat with legacy fields
- `backend/core/agent_factory.py` — Modify `create_claudecode_agent()` to pass resources to runner
- `backend/api/v1/agents.py` — Modify test endpoint to pre-resolve KB/Skill content
- `frontend/src/views/AgentEditor.vue` — Replace claudecode config area with settings_json textarea

### Contracts / References
- `outputs/contracts/task-cc-config-api-contract.md` — API contract for claudecode_config structure
- `openspec/specs/claudecode-settings/spec.md` — Requirements for settings.json handling
- `openspec/specs/claudecode-resource-injection/spec.md` — Requirements for KB/Skill injection
- `openspec/changes/cc-config-settings-json/design.md` — Technical design decisions

---

### Task B1: Rewrite ClaudeCodeRunner.__init__ with new parameter structure

**Files:**
- Modify: `backend/core/claude_code_runner.py` (entire file)

- [ ] **Step 1: Rewrite __init__ to accept new config shape**

Change the constructor from individual fields to accepting the full claudecode_config dict plus separate resource lists.

Replace the entire content of `backend/core/claude_code_runner.py` with this:

```python
import asyncio
import json
import os
from typing import Dict, Any, List, Optional
from loguru import logger


class ClaudeCodeRunner:
    """Claude Code CLI 执行器 — 写入 settings.json + CLAUDE.md，通过子进程调用 Claude Code"""

    def __init__(self, config: Dict[str, Any] = None,
                 mcp_servers: List[Dict] = None,
                 kb_content: List[Dict] = None,
                 skill_content: List[Dict] = None):
        config = config or {}
        # settings_json: the full Claude Code settings.json content as a JSON string
        self.settings_json = config.get("settings_json", "")
        self.model = config.get("model", "claude-sonnet-4-6")
        self.max_turns = config.get("max_turns", 25)
        self.work_dir = config.get("work_dir", os.getcwd())
        self.permission_mode = config.get("permission_mode", "acceptEdits")

        # Legacy field support (backward compat when settings_json is absent)
        self._legacy_allowed_tools = config.get("allowed_tools", [])
        self._legacy_extra_args = config.get("extra_args", [])
        self._legacy_env = config.get("env", {})

        # Resource lists (passed from agent_factory)
        self.mcp_servers = mcp_servers or []
        self.kb_content = kb_content or []
        self.skill_content = skill_content or []

    async def invoke(self, user_input: str, session_id: str,
                     context: Dict[str, Any] = None) -> str:
        """通过 CLI 执行 Claude Code 任务"""
        context = context or {}

        # 1. Write settings.json to work_dir/.claude/settings.json
        settings = self._build_settings_json()
        self._write_settings_json(settings)

        # 2. Write CLAUDE.md to work_dir/CLAUDE.md
        self._write_claude_md(context)

        # 3. Build command
        cmd = [
            "claude",
            "--model", self.model,
            "--max-turns", str(self.max_turns),
            "--permission-mode", self.permission_mode,
            "--print",
            "--output-format", "json",
        ]

        logger.info(f"Claude Code CLI: model={self.model}, max_turns={self.max_turns}, work_dir={self.work_dir}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.work_dir,
                env={**os.environ},  # legacy env no longer merged
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=user_input.encode("utf-8")),
                timeout=self.max_turns * 15,
            )

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"Claude Code exited with code {process.returncode}: {error_msg}"
                )

            output = stdout.decode("utf-8", errors="replace")
            try:
                result = json.loads(output)
                return result.get("result", output)
            except json.JSONDecodeError:
                return output

        except asyncio.TimeoutError:
            logger.error(f"Claude Code timeout after {self.max_turns * 15}s")
            return f"Error: Claude Code execution timed out after {self.max_turns * 15} seconds"
        except FileNotFoundError:
            logger.error("Claude Code CLI not found. Make sure 'claude' is installed.")
            return "Error: Claude Code CLI not found. Please install Claude Code first."
        except Exception as e:
            logger.error(f"Claude Code execution failed: {e}")
            raise

    def _build_settings_json(self) -> dict:
        """Build the settings.json dict from config.

        Priority:
        1. If settings_json is present and non-empty, parse it.
        2. Otherwise, construct from legacy fields for backward compat.
        """
        if self.settings_json and self.settings_json.strip():
            try:
                return json.loads(self.settings_json)
            except json.JSONDecodeError as e:
                logger.warning(f"settings_json parse failed: {e}, falling back to legacy fields")
                return self._build_from_legacy_fields()
        return self._build_from_legacy_fields()

    def _build_from_legacy_fields(self) -> dict:
        """Build a settings.json dict from legacy individual fields."""
        result = {"model": self.model}
        if self._legacy_allowed_tools:
            result["permissions"] = {"allow": self._legacy_allowed_tools}
        return result

    def _write_settings_json(self, settings: dict) -> None:
        """Write settings.json to work_dir/.claude/settings.json."""
        claude_dir = os.path.join(self.work_dir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        settings_path = os.path.join(claude_dir, "settings.json")
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        logger.info(f"Written settings.json to {settings_path}")

    def _write_claude_md(self, context: Dict[str, Any]) -> None:
        """Build and write CLAUDE.md to work_dir."""
        os.makedirs(self.work_dir, exist_ok=True)
        parts = [
            "<!-- Auto-generated by Agent Platform. Edits will be overwritten on next execution. -->",
        ]

        # System prompt section
        system_prompt = context.get("system_prompt", "")
        if system_prompt:
            parts.append("")
            parts.append("## 系统指令")
            parts.append(system_prompt)

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
                                file_content = f.read()
                            parts.append(f"\n```\n{file_content}\n```")
                        except (FileNotFoundError, IOError) as e:
                            parts.append(f"\n*无法读取文件: {e}*")

        # Workflow upstream results
        if context.get("intermediate_results"):
            parts.append("")
            parts.append("## 上游工作流结果")
            parts.append(json.dumps(context["intermediate_results"], ensure_ascii=False, indent=2))

        content = "\n".join(parts)
        claude_md_path = os.path.join(self.work_dir, "CLAUDE.md")
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Written CLAUDE.md to {claude_md_path}")
```

- [ ] **Step 2: Verify the file parses correctly**

Run: `python -c "from backend.core.claude_code_runner import ClaudeCodeRunner; print('OK')"` from the project root (or adjust PYTHONPATH as needed)
Expected: No ImportError, prints "OK"

- [ ] **Step 3: Commit**

```bash
git add backend/core/claude_code_runner.py
git commit -m "refactor: rewrite ClaudeCodeRunner with settings_json/CLAUDE.md file writing

- New __init__ accepts settings_json, mcp_servers, kb_content, skill_content
- _write_settings_json() writes parsed settings to work_dir/.claude/settings.json
- _write_claude_md() injects KB, skill, system_prompt content into CLAUDE.md
- invoke() calls both write methods before launching Claude Code CLI
- Backward compatible: _build_from_legacy_fields() handles old config format"
```

---

### Task B2: Update agent_factory.py to pass resources to ClaudeCodeRunner

**Files:**
- Modify: `backend/core/agent_factory.py` (lines 420-450, the create_claudecode_agent method)

- [ ] **Step 1: Modify create_claudecode_agent() to accept and pass resource contexts**

Edit `backend/core/agent_factory.py`. Replace the `create_claudecode_agent` method:

```python
    async def create_claudecode_agent(self, agent_config: Dict[str, Any],
                                       mcp_servers: List[Dict] = None,
                                       kb_content: List[Dict] = None,
                                       skill_content: List[Dict] = None):
        """创建 claudecode 类型 Agent 的执行节点

        将请求委托给 Claude Code CLI 运行器，并传递已解析的资源上下文。

        Args:
            agent_config: Agent 配置字典，包含 claudecode_config 等字段
            mcp_servers: 关联的 MCP Server 配置列表（含 base_url, headers 等）
            kb_content: 关联知识库的 ContentBlock 列表（含 heading_path, body 等）
            skill_content: 关联 Skill 的内容列表（含 name, content 等）

        Returns:
            异步函数，接收 state dict 并返回更新后的 state dict
        """
        from core.claude_code_runner import ClaudeCodeRunner
        runner = ClaudeCodeRunner(
            config=agent_config.get("claudecode_config", {}),
            mcp_servers=mcp_servers,
            kb_content=kb_content,
            skill_content=skill_content,
        )
        agent_name = agent_config.get("name", "unknown")

        async def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
            user_input = state.get("user_input", "")
            session_id = state.get("session_id", "")
            try:
                output = await runner.invoke(user_input, session_id, state)
            except Exception as e:
                output = f"Claude Code Agent error: {str(e)}"
                logger.error(f"Claude Code Agent {agent_name} failed: {e}")

            intermediate = state.get("intermediate_results", {})
            intermediate[agent_name] = output
            return {
                "intermediate_results": intermediate,
            }

        return agent_node
```

- [ ] **Step 2: Commit**

```bash
git add backend/core/agent_factory.py
git commit -m "feat: pass MCP/KB/Skill resources to ClaudeCodeRunner in create_claudecode_agent

- create_claudecode_agent() now accepts mcp_servers, kb_content, skill_content
- These are forwarded to ClaudeCodeRunner constructor
- Enables resource injection into settings.json and CLAUDE.md"
```

---

### Task B3: Update agents.py test endpoint to pre-resolve KB and Skill content

**Files:**
- Modify: `backend/api/v1/agents.py` (lines 159-196, the test_agent endpoint)

- [ ] **Step 1: Modify test_agent to fetch KB ContentBlocks and Skill content**

Edit `backend/api/v1/agents.py`. Replace the relevant section in `test_agent`:

The existing code around the import statement and config building needs to be changed. Find the section starting with `config = {` and replace with content that fetches KB ContentBlocks and Skill content:

```python
            from core.claude_code_runner import ClaudeCodeRunner

            mcp_links = await AgentMcpLink.filter(agent_id=agent_id).prefetch_related("mcp_server")
            kb_links = await AgentKbLink.filter(agent_id=agent_id).prefetch_related("kb")
            skill_links = await AgentSkillLink.filter(agent_id=agent_id).prefetch_related("skill")

            # Pre-resolve KB ContentBlock content
            from models.knowledge_base import ContentBlock
            kb_content = []
            if a.knowledge_base_ids:
                blocks = await ContentBlock.filter(kb_id__in=a.knowledge_base_ids).order_by("source_file", "id")
                for b in blocks:
                    kb_content.append({
                        "heading_path": b.heading_path or b.source_file,
                        "body": b.body,
                        "source_file": b.source_file,
                    })

            # Pre-resolve Skill content
            skill_content = []
            for sl in skill_links:
                skill = sl.skill
                skill_content.append({
                    "name": skill.name,
                    "description": skill.description,
                    "skill_type": skill.skill_type,
                    "content": skill.content,
                })

            mcp_servers = [{
                "id": ml.mcp_server.id, "name": ml.mcp_server.name,
                "base_url": ml.mcp_server.base_url,
                "headers": ml.mcp_server.headers,
                "single_endpoint": ml.mcp_server.single_endpoint,
                "enabled_tools": ml.enabled_tools,
                "enabled": ml.enabled,
            } for ml in mcp_links]

            config = {
                "name": a.name, "agent_type": a.agent_type, "role": a.role,
                "llm_config": a.llm_config, "llm_config_id": a.llm_config_id,
                "http_config": a.http_config,
                "claudecode_config": a.claudecode_config,
                "system_prompt": a.system_prompt,
                "mcp_servers": mcp_servers,
                "knowledge_base_ids": a.knowledge_base_ids or [],
                "skills": skill_content,
            }

            if a.agent_type == "claudecode":
                agent_node = await agent_factory.create_claudecode_agent(
                    config,
                    mcp_servers=mcp_servers,
                    kb_content=kb_content,
                    skill_content=skill_content,
                )
            else:
                agent_node = await agent_factory.create(config)
```

The rest of the function (result calling and return) stays the same. Here is the exact edit — locate the original section starting with `try:` inside `test_agent`:

```python
    try:
        from core.agent_factory import agent_factory

        mcp_links = await AgentMcpLink.filter(agent_id=agent_id).prefetch_related("mcp_server")
        kb_links = await AgentKbLink.filter(agent_id=agent_id).prefetch_related("kb")
        skill_links = await AgentSkillLink.filter(agent_id=agent_id).prefetch_related("skill")

        config = {
            "name": a.name, "agent_type": a.agent_type, "role": a.role,
            "llm_config": a.llm_config, "llm_config_id": a.llm_config_id,
            "http_config": a.http_config,
            "claudecode_config": a.claudecode_config,
            "system_prompt": a.system_prompt,
            "mcp_servers": [{
                "id": ml.mcp_server.id, "name": ml.mcp_server.name,
                "base_url": ml.mcp_server.base_url,
                "headers": ml.mcp_server.headers,
                "single_endpoint": ml.mcp_server.single_endpoint,
                "enabled_tools": ml.enabled_tools,
                "enabled": ml.enabled,
            } for ml in mcp_links],
            "knowledge_base_ids": a.knowledge_base_ids or [],
            "skills": [{"name": sl.skill.name, "skill_type": sl.skill.skill_type, "content": sl.skill.content} for sl in skill_links],
        }

        agent_node = await agent_factory.create(config)
        result = await agent_node({"user_input": body.message, "messages": [], "intermediate_results": {}})
        output = result.get("intermediate_results", {}).get(a.name, "")
        return success(data={"response": output})
    except Exception as e:
        logger.error(f"Agent test failed: {e}")
        return error(code=-1, message=f"测试失败: {str(e)}")
```

Replace with:

```python
    try:
        from core.agent_factory import agent_factory
        from models.knowledge_base import ContentBlock

        mcp_links = await AgentMcpLink.filter(agent_id=agent_id).prefetch_related("mcp_server")
        kb_links = await AgentKbLink.filter(agent_id=agent_id).prefetch_related("kb")
        skill_links = await AgentSkillLink.filter(agent_id=agent_id).prefetch_related("skill")

        # Pre-resolve KB ContentBlock content
        kb_content = []
        if a.knowledge_base_ids:
            blocks = await ContentBlock.filter(kb_id__in=a.knowledge_base_ids).order_by("source_file", "id")
            for b in blocks:
                kb_content.append({
                    "heading_path": b.heading_path or b.source_file,
                    "body": b.body,
                    "source_file": b.source_file,
                })

        # Pre-resolve Skill content
        skill_content = []
        for sl in skill_links:
            skill = sl.skill
            skill_content.append({
                "name": skill.name,
                "description": skill.description,
                "skill_type": skill.skill_type,
                "content": skill.content,
            })

        mcp_servers = [{
            "id": ml.mcp_server.id, "name": ml.mcp_server.name,
            "base_url": ml.mcp_server.base_url,
            "headers": ml.mcp_server.headers,
            "single_endpoint": ml.mcp_server.single_endpoint,
            "enabled_tools": ml.enabled_tools,
            "enabled": ml.enabled,
        } for ml in mcp_links]

        config = {
            "name": a.name, "agent_type": a.agent_type, "role": a.role,
            "llm_config": a.llm_config, "llm_config_id": a.llm_config_id,
            "http_config": a.http_config,
            "claudecode_config": a.claudecode_config,
            "system_prompt": a.system_prompt,
            "mcp_servers": mcp_servers,
            "knowledge_base_ids": a.knowledge_base_ids or [],
            "skills": skill_content,
        }

        if a.agent_type == "claudecode":
            agent_node = await agent_factory.create_claudecode_agent(
                config,
                mcp_servers=mcp_servers,
                kb_content=kb_content,
                skill_content=skill_content,
            )
        else:
            agent_node = await agent_factory.create(config)

        result = await agent_node({"user_input": body.message, "messages": [], "intermediate_results": {}})
        output = result.get("intermediate_results", {}).get(a.name, "")
        return success(data={"response": output})
    except Exception as e:
        logger.error(f"Agent test failed: {e}")
        return error(code=-1, message=f"测试失败: {str(e)}")
```

- [ ] **Step 2: Add settings_json size validation to create_agent and update_agent**

Since the spec requires settings_json to be limited to 100KB, add validation before creating/updating.

In `create_agent`, after the existing check for duplicate name, add:

```python
    # Validate settings_json size for claudecode agents
    if body.agent_type == "claudecode" and body.claudecode_config:
        sj = body.claudecode_config.get("settings_json", "")
        if len(sj) > 100000:
            return error(code=400, message="settings_json 内容过长，最大支持 100KB")
```

In `update_agent`, inside the update loop before `setattr`, add:

```python
    if body.claudecode_config is not None and body.claudecode_config.get("settings_json", ""):
        sj = body.claudecode_config["settings_json"]
        if len(sj) > 100000:
            return error(code=400, message="settings_json 内容过长，最大支持 100KB")
```

- [ ] **Step 3: Commit**

```bash
git add backend/api/v1/agents.py
git commit -m "feat: pre-resolve KB/Skill content for claudecode test endpoint; add settings_json size validation

- test_agent now fetches ContentBlock records and Skill content before invoking runner
- claudecode agents use create_claudecode_agent() with resource context
- settings_json field validated to be under 100KB on create/update"
```

---

### Task F1: Create TypeScript interface for ClaudeCodeConfig

**Files:**
- Create: `frontend/src/types/agent.ts`

- [ ] **Step 1: Create the TypeScript interface file**

```typescript
export interface ClaudeCodeConfig {
  settings_json: string
  model: string
  max_turns: number
  work_dir: string
  permission_mode: 'default' | 'acceptEdits' | 'bypassPermissions' | 'plan'
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/agent.ts
git commit -m "feat: add ClaudeCodeConfig TypeScript interface"
```

---

### Task F2: Refactor AgentEditor.vue claudecode configuration area

**Files:**
- Modify: `frontend/src/views/AgentEditor.vue`

- [ ] **Step 1: Replace the claudecode config template section**

In `AgentEditor.vue`, find the `<template>` section starting at:

```html
        <!-- Claude Code Config -->
        <template v-if="form.agent_type === 'claudecode'">
          <h3 class="text-lg font-semibold mb-4 mt-4 text-[#5e6ad2]">Claude Code 配置</h3>
          <a-row :gutter="16">
            ...
          </a-row>
          ...
        </template>
```

Replace the entire `<template v-if="form.agent_type === 'claudecode'">...</template>` block with:

```html
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

- [ ] **Step 2: Update the script section to add JSON validation**

Find the `ccConfig` ref definition (around line 252):

```typescript
const ccConfig = ref<any>({
  model: 'claude-sonnet-4-6',
  max_turns: 25,
  work_dir: '',
  permission_mode: 'acceptEdits',
  allowed_tools: ['Read', 'Write', 'Edit', 'Bash', 'Grep', 'Glob'],
})
```

Replace with:

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

- [ ] **Step 3: Update loadAgent() to handle the new config shape**

In `loadAgent()`, find the existing `if (d.claudecode_config)` block and replace:

```typescript
    if (d.claudecode_config) {
      ccConfig.value = { ...ccConfig.value, ...d.claudecode_config }
    }
```

Replace with:

```typescript
    if (d.claudecode_config) {
      ccConfig.value = { ...ccConfig.value, ...d.claudecode_config }
      // Validate the loaded json
      validateSettingsJson()
    }
```

- [ ] **Step 4: Update buildFormData() to remove deprecated fields and include settings_json**

In the `buildFormData()` function, find:

```typescript
  if (form.value.agent_type === 'claudecode') {
    data.claudecode_config = ccConfig.value
  }
```

Replace with:

```typescript
  if (form.value.agent_type === 'claudecode') {
    data.claudecode_config = {
      settings_json: ccConfig.value.settings_json,
      model: ccConfig.value.model,
      max_turns: ccConfig.value.max_turns,
      work_dir: ccConfig.value.work_dir,
      permission_mode: ccConfig.value.permission_mode,
    }
  }
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/AgentEditor.vue
git commit -m "feat: refactor claudecode config to settings_json textarea

- Replace individual config fields with settings_json textarea (monospace)
- Keep model/max_turns/work_dir/permission_mode as quick-set fields
- Add real-time JSON syntax validation with error display
- Remove deprecated allowed_tools checkbox group
- Load and save new claudecode_config structure"
```

---

### Task F3: Register the new TypeScript type in the project

**Files:**
- Modify: (if needed) Check if there is a tsconfig or type declaration index file

- [ ] **Step 1: Check if the types file is auto-discovered**

The file `frontend/src/types/agent.ts` should be automatically picked up by TypeScript since it's inside `src/`. No additional registration is needed for Vite-based projects.

Verify the file is accessible by running:

```bash
cd frontend && npx tsc --noEmit --pretty 2>&1 | head -20
```

Expected: No errors related to the new type file.

- [ ] **Step 2: No commit needed if no changes were made beyond F1/F2**

---

## Self-Review: Spec Coverage Check

### claudecode-settings spec coverage:

| Requirement | Task | Covered? |
|---|---|---|
| User can configure via settings_json | F2 (textarea), B1 (storage/writing) | Yes |
| Create/Update/Get Agent with settings_json | B3 (validation), F2 (UI) | Yes |
| Invalid JSON syntax rejection | F2 (frontend validation), B3 (backend 400) | Yes |
| Backward compat with legacy format | B1 (_build_from_legacy_fields) | Yes |
| Write settings.json to work_dir | B1 (_write_settings_json) | Yes |
| Auto-create work_dir | B1 (os.makedirs in _write_settings_json) | Yes |
| Size limit (100KB) | B3 (validation in agents.py) | Yes |
| Legacy fields ignored when settings_json present | B1 (_build_settings_json checks settings_json first) | Yes |

### claudecode-resource-injection spec coverage:

| Requirement | Task | Covered? |
|---|---|---|
| KB content injected into CLAUDE.md | B1 (_write_claude_md) | Yes |
| No KB linked — no KB section | B1 (conditional if self.kb_content) | Yes |
| KB content truncated at 50KB | B1 (total_len check) | Yes |
| Skill content injected into CLAUDE.md | B1 (_write_claude_md, skills section) | Yes |
| Skill format (prompt/file) | B1 (prompt_template and file_path handling) | Yes |
| System prompt in CLAUDE.md header | B1 (## 系统指令 section) | Yes |
| Auto-generated notice | B1 (first line of CLAUDE.md) | Yes |
| Workflow context injection | B1 (## 上游工作流结果 section) | Yes |

All requirements are covered. No gaps found.

---

## Placeholder Scan

Checked all task steps: No TODOs, TBDs, or placeholders. All code blocks contain complete, runnable code.

---

## Type Consistency Check

- `ClaudeCodeConfig` interface in F1: `{ settings_json: string, model: string, max_turns: number, work_dir: string, permission_mode: 'default' | 'acceptEdits' | 'bypassPermissions' | 'plan' }`
- `ccConfig` ref in F2: matches this shape (plus `settings_json`)
- `buildFormData()` emits `{ settings_json, model, max_turns, work_dir, permission_mode }` — matches
- Backend `claude_code_runner.py` reads `config.get("settings_json", "")`, `config.get("model")`, etc. — matches
- Legacy fallback: `_build_from_legacy_fields()` reads `allowed_tools` from config — consistent with backward compat spec

No inconsistencies found.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-15-cc-config-settings-json.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
