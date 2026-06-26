import json
import os
import time as time_mod
from typing import Dict, Any, List, Optional

from loguru import logger

from core.session_manager import session_manager
from core.agent_call_log import agent_call_logger


class ClaudeCodeRunner:
    """Claude Code executor supporting two modes:

    1. New mode (registry references): claudecode_config = {"project_registry_id": int, "settings_registry_id": int}
       Queries registries for Git info and execution config, uses claude-code-sdk.

    2. Legacy mode (inline config): Uses config fields like settings_json, model, work_dir directly.
       Falls back to CLI subprocess for backward compatibility.

    Workspace layout (new mode):
      {session_workspace}/
        projects/{project_name}/code/    ← 按项目名组织的代码（同 session 多 agent 共享）
        agents/{agent_name}/             ← 当前 agent 工作区（cwd + CLAUDE.md）
    """

    def __init__(self, config: Dict[str, Any] = None,
                 mcp_servers: List[Dict] = None,
                 kb_content: List[Dict] = None,
                 skill_content: List[Dict] = None,
                 agent_name: str = "unknown",
                 system_prompt: str = ""):
        self.config = config or {}
        self.mcp_servers = mcp_servers or []
        self.kb_content = kb_content or []
        self.skill_content = skill_content or []
        self.agent_name = agent_name
        self.system_prompt = system_prompt

    async def invoke(self, user_input: str, session_id: str,
                     context: Dict[str, Any] = None,
                     trace_id: str = None,
                     parent_span_id: str = None) -> str:
        """Execute a Claude Code task.

        Args:
            user_input: Task description from the user
            session_id: Session identifier
            context: Additional context including system_prompt, intermediate_results,
                     session_workspace
            trace_id: Agent call trace ID (for logging)
            parent_span_id: Parent span ID (for logging hierarchy)

        Returns:
            Claude Code execution result text
        """
        context = context or {}

        has_registry_refs = (
            self.config.get("project_registry_id") and
            self.config.get("settings_registry_id")
        )

        if has_registry_refs:
            return await self._invoke_with_registries(
                user_input, session_id, context,
                trace_id=trace_id, parent_span_id=parent_span_id,
            )
        else:
            return await self._invoke_legacy(
                user_input, session_id, context,
                trace_id=trace_id, parent_span_id=parent_span_id,
            )

    # ------------------------------------------------------------------
    # New mode: project_registry + settings_registry
    # ------------------------------------------------------------------

    async def _invoke_with_registries(self, user_input: str, session_id: str,
                                       context: Dict[str, Any],
                                       trace_id: str = None,
                                       parent_span_id: str = None) -> str:
        """New mode: resolve config from registries, use claude-code-sdk."""
        project_registry_id = self.config.get("project_registry_id")
        settings_registry_id = self.config.get("settings_registry_id")

        from models.project_registry import ProjectRegistry
        from models.claude_settings import ClaudeSettingsRegistry

        project = await ProjectRegistry.get_or_none(id=project_registry_id)
        settings = await ClaudeSettingsRegistry.get_or_none(id=settings_registry_id)

        if not project:
            logger.error(f"ProjectRegistry id={project_registry_id} not found for agent {self.agent_name}")
            return f"Error: Project config not found (id={project_registry_id})"

        if not settings:
            logger.error(f"ClaudeSettingsRegistry id={settings_registry_id} not found for agent {self.agent_name}")
            return f"Error: Claude settings not found (id={settings_registry_id})"

        # --- Derive paths from session workspace ---
        session_workspace = (context or {}).get("session_workspace", "")
        if not session_workspace:
            logger.warning(f"No session_workspace in context, falling back to legacy workspace path")
            from core.git_ops import get_workspace_path
            workspace_dir = str(get_workspace_path(project))
            self._write_claude_md(workspace_dir, context, project.system_prompt)
            return await self._run_fallback(
                workspace_dir, user_input, settings, project, context,
                trace_id=trace_id, parent_span_id=parent_span_id,
            )

        project_code_path = session_manager.get_project_code_path(session_id, project.name)
        agent_workspace = session_manager.ensure_agent_workspace(session_id, self.agent_name)

        # --- Ensure code exists (skip git if already there) ---
        from core.git_ops import ensure_code_exists
        force_pull = self._needs_code_pull(context)
        ensure_code_exists(project, project_code_path, force_pull=force_pull)

        # --- Write CLAUDE.md to session workspace root (cwd for SDK) ---
        self._write_claude_md(session_workspace, context, project.system_prompt,
                              project_code_path=project_code_path)

        # --- Write .claude/settings.json for permissions ---
        self._write_claude_settings(session_workspace, settings)

        # cwd 使用 session_workspace 根目录，让 agent 可以访问项目代码和自身工作区
        cwd_for_sdk = session_workspace

        try:
            return await self._run_sdk(
                workspace_dir=cwd_for_sdk,
                user_input=user_input,
                settings=settings,
                project=project,
                context=context,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )
        except ImportError:
            logger.warning("claude-code-sdk not installed, falling back to legacy CLI")
            return await self._run_cli_legacy(
                agent_workspace, user_input, settings,
                trace_id=trace_id, parent_span_id=parent_span_id,
            )
        except Exception as e:
            logger.error(f"Claude Code SDK execution failed: {e}")
            return f"Error: Claude Code execution failed - {e}"

    def _needs_code_pull(self, context: Dict[str, Any]) -> bool:
        """判断当前是否需要拉取最新代码。

        条件：系统提示词中包含明确的代码处理要求。
        """
        prompts_to_check = [self.system_prompt, context.get("system_prompt", "")]
        code_keywords = ["修改代码", "修复", "新增功能", "编写", "改代码",
                         "create", "modify", "fix", "implement", "write code"]
        for prompt in prompts_to_check:
            if any(kw in prompt for kw in code_keywords):
                logger.info(f"Agent {self.agent_name} prompt 包含代码处理关键词，强制拉取最新代码")
                return True
        return False

    # ------------------------------------------------------------------
    # SDK execution
    # ------------------------------------------------------------------

    async def _run_sdk(self, workspace_dir: str, user_input: str,
                        settings, project, context: Dict[str, Any],
                        trace_id: str = None,
                        parent_span_id: str = None) -> str:
        """Execute Claude Code using claude-code-sdk."""
        from claude_code_sdk import ClaudeSDKClient, ClaudeCodeOptions
        from claude_code_sdk.types import (
            ResultMessage, AssistantMessage, TextBlock, ToolUseBlock,
            PermissionResultAllow, ToolPermissionContext,
        )

        # Auto-approve callback — 作为 Supervisor 代理用户批准所有工具调用
        async def _auto_approve_tool(
            tool_name: str,
            tool_input: dict,
            permission_context: ToolPermissionContext,
        ) -> PermissionResultAllow:
            logger.info(f"[Claude Code] Auto-approved tool: {tool_name}")
            return PermissionResultAllow()

        options_kwargs = {
            "permission_mode": settings.permission_mode,
            "cwd": workspace_dir,
            "max_turns": settings.max_turns,
            "can_use_tool": _auto_approve_tool,
        }

        extra_settings = {}
        if settings.settings_json and settings.settings_json.strip():
            try:
                extra_settings = json.loads(settings.settings_json)
            except json.JSONDecodeError:
                pass

        # 先加载环境变量（ANTHROPIC_MODEL 等可能在 env 中）
        env_vars = extra_settings.get("env", {})
        if env_vars:
            for k, v in env_vars.items():
                os.environ[k] = v
            logger.info(f"Loaded {len(env_vars)} env vars from settings_json")

        # 模型优先级: env.ANTHROPIC_MODEL > settings_json.model > settings.model
        env_model = env_vars.get("ANTHROPIC_MODEL")
        if env_model:
            options_kwargs["model"] = env_model
        elif extra_settings.get("model"):
            options_kwargs["model"] = extra_settings["model"]
        elif settings.model:
            options_kwargs["model"] = settings.model

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

        # Build system_prompt for Agent call logging
        _system_prompt = "\n\n".join(system_prompt_parts) if system_prompt_parts else ""
        _trace_id = trace_id or ""
        _span_id = agent_call_logger.start_span(parent_span_id) if _trace_id else ""
        _t0 = time_mod.time()

        logger.info(f"Claude Code SDK: model={options_kwargs.get('model')}, "
                     f"max_turns={settings.max_turns}, cwd={workspace_dir}, "
                     f"timeout={timeout_seconds}s")

        client = ClaudeSDKClient(options)
        await client.connect()

        try:
            last_text = ""
            await client.query(user_input)

            while True:
                got_result = False
                has_question = False

                async for message in client.receive_response():
                    if hasattr(message, 'content') and not isinstance(message, ResultMessage):
                        if isinstance(message, AssistantMessage):
                            for block in message.content:
                                if isinstance(block, TextBlock) and block.text.strip():
                                    last_text = block.text
                                elif isinstance(block, ToolUseBlock) and block.name == "AskUserQuestion":
                                    # Auto-answer — 代理用户批准
                                    has_question = True
                                    logger.info(
                                        f"[Claude Code] Auto-answering AskUserQuestion: "
                                        f"{str(block.input)[:200]}"
                                    )

                    elif isinstance(message, ResultMessage):
                        result = message.result
                        is_error = message.is_error
                        got_result = True

                        if is_error:
                            logger.warning(f"Claude Code returned error: {result}")
                            _elapsed = int((time_mod.time() - _t0) * 1000)
                            if _trace_id:
                                agent_call_logger.log_agent_call(
                                    trace_id=_trace_id, parent_span_id=parent_span_id,
                                    span_id=_span_id, agent_name=self.agent_name,
                                    agent_type="claudecode", system_prompt=_system_prompt,
                                    user_input=user_input, output=result,
                                    duration_ms=_elapsed,
                                    metadata={"error": True, "mode": "sdk"},
                                )
                            return f"Claude Code execution error: {result}"

                        _elapsed = int((time_mod.time() - _t0) * 1000)
                        _final_output = result or last_text or "Execution completed (no output)"
                        if _trace_id:
                            agent_call_logger.log_agent_call(
                                trace_id=_trace_id, parent_span_id=parent_span_id,
                                span_id=_span_id, agent_name=self.agent_name,
                                agent_type="claudecode", system_prompt=_system_prompt,
                                user_input=user_input, output=_final_output,
                                duration_ms=_elapsed,
                                metadata={"mode": "sdk"},
                            )
                        logger.info(f"Claude Code completed: cost={getattr(message, 'total_cost_usd', 'N/A')}")
                        return _final_output

                if got_result:
                    break

                if has_question:
                    # 有 AskUserQuestion 但未收到 ResultMessage，发送批准后继续
                    await client.query("yes, please proceed with the task")
                    continue

                # 没有新消息，退出
                break

            return last_text or "Execution completed (no output)"

        except Exception as e:
            logger.error(f"SDK execution error: {e}")
            raise
        finally:
            await client.disconnect()

    # ------------------------------------------------------------------
    # CLI fallback
    # ------------------------------------------------------------------

    async def _run_cli_legacy(self, workspace_dir: str, user_input: str,
                               settings,
                               trace_id: str = None,
                               parent_span_id: str = None) -> str:
        """Fallback to CLI subprocess execution."""
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

        # Read CLAUDE.md as the system_prompt for logging
        _system_prompt = ""
        _claude_md_path = os.path.join(workspace_dir, "CLAUDE.md")
        try:
            with open(_claude_md_path, "r", encoding="utf-8") as _f:
                _system_prompt = _f.read()
        except (FileNotFoundError, IOError):
            pass
        _trace_id = trace_id or ""
        _span_id = agent_call_logger.start_span(parent_span_id) if _trace_id else ""
        _t0 = time_mod.time()

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
                _elapsed = int((time_mod.time() - _t0) * 1000)
                if _trace_id:
                    agent_call_logger.log_agent_call(
                        trace_id=_trace_id, parent_span_id=parent_span_id,
                        span_id=_span_id, agent_name=self.agent_name,
                        agent_type="claudecode", system_prompt=_system_prompt,
                        user_input=user_input, output=error_msg,
                        duration_ms=_elapsed,
                        metadata={"error": True, "mode": "cli_legacy"},
                    )
                raise RuntimeError(f"Claude Code exited with code {process.returncode}: {error_msg}")

            output = stdout.decode("utf-8", errors="replace")
            try:
                result = json.loads(output)
                _final_output = result.get("result", output)
            except json.JSONDecodeError:
                _final_output = output

            _elapsed = int((time_mod.time() - _t0) * 1000)
            if _trace_id:
                agent_call_logger.log_agent_call(
                    trace_id=_trace_id, parent_span_id=parent_span_id,
                    span_id=_span_id, agent_name=self.agent_name,
                    agent_type="claudecode", system_prompt=_system_prompt,
                    user_input=user_input, output=_final_output,
                    duration_ms=_elapsed,
                    metadata={"mode": "cli_legacy"},
                )
            return _final_output

        except asyncio.TimeoutError:
            _elapsed = int((time_mod.time() - _t0) * 1000)
            if _trace_id:
                agent_call_logger.log_agent_call(
                    trace_id=_trace_id, parent_span_id=parent_span_id,
                    span_id=_span_id, agent_name=self.agent_name,
                    agent_type="claudecode", system_prompt=_system_prompt,
                    user_input=user_input, output="",
                    duration_ms=_elapsed,
                    metadata={"error": True, "mode": "cli_legacy", "timeout": True},
                )
            logger.error("Claude Code CLI timed out")
            return "Error: Claude Code execution timed out"

    async def _run_fallback(self, workspace_dir: str, user_input: str,
                             settings, project, context: Dict[str, Any],
                             trace_id: str = None,
                             parent_span_id: str = None) -> str:
        """Fallback when no session_workspace is available (legacy behavior)."""
        from core.git_ops import clone_or_pull_repo
        try:
            clone_or_pull_repo(project)
        except Exception as e:
            logger.error(f"Git clone failed for {project.name}: {e}")
            return f"Error: Git clone failed - {e}"

        try:
            return await self._run_sdk(
                workspace_dir=workspace_dir,
                user_input=user_input,
                settings=settings,
                project=project,
                context=context,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )
        except ImportError:
            return await self._run_cli_legacy(
                workspace_dir, user_input, settings,
                trace_id=trace_id, parent_span_id=parent_span_id,
            )
        except Exception as e:
            logger.error(f"Claude Code execution failed: {e}")
            return f"Error: Claude Code execution failed - {e}"

    # ------------------------------------------------------------------
    # Legacy inline mode
    # ------------------------------------------------------------------

    async def _invoke_legacy(self, user_input: str, session_id: str,
                              context: Dict[str, Any],
                              trace_id: str = None,
                              parent_span_id: str = None) -> str:
        """Legacy mode: use inline config fields for backward compatibility."""
        import asyncio

        session_workspace = (context or {}).get("session_workspace", "")

        settings_json = self.config.get("settings_json", "")
        model = self.config.get("model", "claude-sonnet-4-6")
        max_turns = self.config.get("max_turns", 25)
        permission_mode = self.config.get("permission_mode", "acceptEdits")

        # Determine work_dir: prefer session agent workspace
        if session_workspace and session_id:
            work_dir = session_manager.ensure_agent_workspace(session_id, self.agent_name)
        else:
            work_dir = self.config.get("work_dir", "")
            if not work_dir:
                work_dir = os.getcwd()

        claude_dir = os.path.join(work_dir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        if settings_json and settings_json.strip():
            try:
                settings_dict = json.loads(settings_json)
                with open(os.path.join(claude_dir, "settings.json"), "w", encoding="utf-8") as f:
                    json.dump(settings_dict, f, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                pass

        self._write_claude_md(work_dir, context)

        cmd = [
            "claude",
            "--model", model,
            "--max-turns", str(max_turns),
            "--permission-mode", permission_mode,
            "--print",
            "--output-format", "json",
        ]

        logger.info(f"Claude Code CLI (legacy): model={model}, max_turns={max_turns}, work_dir={work_dir}")

        # Read CLAUDE.md as system_prompt for logging
        _system_prompt = ""
        _claude_md_path = os.path.join(work_dir, "CLAUDE.md")
        try:
            with open(_claude_md_path, "r", encoding="utf-8") as _f:
                _system_prompt = _f.read()
        except (FileNotFoundError, IOError):
            pass
        _trace_id = trace_id or ""
        _span_id = agent_call_logger.start_span(parent_span_id) if _trace_id else ""
        _t0 = time_mod.time()

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
                _elapsed = int((time_mod.time() - _t0) * 1000)
                if _trace_id:
                    agent_call_logger.log_agent_call(
                        trace_id=_trace_id, parent_span_id=parent_span_id,
                        span_id=_span_id, agent_name=self.agent_name,
                        agent_type="claudecode", system_prompt=_system_prompt,
                        user_input=user_input, output=error_msg,
                        duration_ms=_elapsed,
                        metadata={"error": True, "mode": "cli_legacy_inline"},
                    )
                raise RuntimeError(f"Claude Code exited with code {process.returncode}: {error_msg}")

            output = stdout.decode("utf-8", errors="replace")
            try:
                result = json.loads(output)
                _final_output = result.get("result", output)
            except json.JSONDecodeError:
                _final_output = output

            _elapsed = int((time_mod.time() - _t0) * 1000)
            if _trace_id:
                agent_call_logger.log_agent_call(
                    trace_id=_trace_id, parent_span_id=parent_span_id,
                    span_id=_span_id, agent_name=self.agent_name,
                    agent_type="claudecode", system_prompt=_system_prompt,
                    user_input=user_input, output=_final_output,
                    duration_ms=_elapsed,
                    metadata={"mode": "cli_legacy_inline"},
                )
            return _final_output

        except asyncio.TimeoutError:
            _elapsed = int((time_mod.time() - _t0) * 1000)
            if _trace_id:
                agent_call_logger.log_agent_call(
                    trace_id=_trace_id, parent_span_id=parent_span_id,
                    span_id=_span_id, agent_name=self.agent_name,
                    agent_type="claudecode", system_prompt=_system_prompt,
                    user_input=user_input, output="",
                    duration_ms=_elapsed,
                    metadata={"error": True, "mode": "cli_legacy_inline", "timeout": True},
                )
            logger.error(f"Claude Code timeout after {max_turns * 15}s")
            return f"Error: Claude Code execution timed out after {max_turns * 15} seconds"
        except FileNotFoundError:
            _elapsed = int((time_mod.time() - _t0) * 1000)
            if _trace_id:
                agent_call_logger.log_agent_call(
                    trace_id=_trace_id, parent_span_id=parent_span_id,
                    span_id=_span_id, agent_name=self.agent_name,
                    agent_type="claudecode", system_prompt=_system_prompt,
                    user_input=user_input, output="",
                    duration_ms=_elapsed,
                    metadata={"error": True, "mode": "cli_legacy_inline", "detail": "claude CLI not found"},
                )
            logger.error("Claude Code CLI not found")
            return "Error: Claude Code CLI not found"
        except Exception as e:
            _elapsed = int((time_mod.time() - _t0) * 1000)
            if _trace_id:
                agent_call_logger.log_agent_call(
                    trace_id=_trace_id, parent_span_id=parent_span_id,
                    span_id=_span_id, agent_name=self.agent_name,
                    agent_type="claudecode", system_prompt=_system_prompt,
                    user_input=user_input, output=str(e),
                    duration_ms=_elapsed,
                    metadata={"error": True, "mode": "cli_legacy_inline"},
                )
            logger.error(f"Claude Code execution failed: {e}")
            raise

    # ------------------------------------------------------------------
    # CLAUDE.md writer
    # ------------------------------------------------------------------

    def _write_claude_md(self, work_dir: str, context: Dict[str, Any] = None,
                          extra_system_prompt: str = None,
                          project_code_path: str = None) -> None:
        """Build and write CLAUDE.md to work_dir.

        If project_code_path is provided, adds a reference so the LLM
        knows where to find the project code on disk.
        """
        context = context or {}
        os.makedirs(work_dir, exist_ok=True)

        parts = [
            "<!-- Auto-generated by Agent Platform. Edits will be overwritten on next execution. -->",
        ]

        system_prompt = context.get("system_prompt", "")
        if system_prompt:
            parts.append("")
            parts.append("## System Instructions")
            parts.append(system_prompt)
        if extra_system_prompt:
            parts.append("")
            parts.append("## Project Instructions")
            parts.append(extra_system_prompt)

        # Project code path reference (same session, potentially shared across agents)
        if project_code_path:
            parts.append("")
            parts.append("## Project Code")
            parts.append(f"项目代码位于: {project_code_path}")
            parts.append("请使用 Read / Edit / Bash 等工具在此目录下操作代码。")

        if self.kb_content:
            parts.append("")
            parts.append("## Knowledge Base")
            total_len = 0
            max_kb_bytes = 50000
            for block in self.kb_content:
                heading = block.get("heading_path", block.get("source_file", "Unknown"))
                body = block.get("body", "")
                chunk = f"\n### {heading}\n{body}"
                if total_len + len(chunk) > max_kb_bytes:
                    parts.append("\n--- Knowledge base truncated (50KB limit) ---")
                    break
                parts.append(chunk)
                total_len += len(chunk)

        if self.skill_content:
            parts.append("")
            parts.append("## Available Skills")
            for skill in self.skill_content:
                name = skill.get("name", "Unknown")
                desc = skill.get("description", "")
                skill_type = skill.get("skill_type", "prompt")
                content = skill.get("content", {})
                parts.append(f"\n### {name}")
                if desc:
                    parts.append(f"Description: {desc}")
                if skill_type == "prompt":
                    template = content.get("prompt_template", "") if isinstance(content, dict) else ""
                    if template:
                        parts.append(f"\n{template}")
                elif skill_type == "file":
                    file_path = content.get("file_path", "") if isinstance(content, dict) else ""
                    if file_path:
                        parts.append(f"Reference file: {file_path}")
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                parts.append(f"\n```\n{f.read()}\n```")
                        except (FileNotFoundError, IOError) as e:
                            parts.append(f"\n*Cannot read file: {e}*")

        if context.get("intermediate_results"):
            parts.append("")
            parts.append("## Upstream Workflow Results")
            parts.append(json.dumps(context["intermediate_results"], ensure_ascii=False, indent=2))

        content = "\n".join(parts)
        claude_md_path = os.path.join(work_dir, "CLAUDE.md")
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Written CLAUDE.md to {claude_md_path} (code path: {project_code_path or 'N/A'})")

    def _write_claude_settings(self, work_dir: str, settings) -> None:
        """将 settings_json 中的权限配置写入 .claude/settings.json"""
        if not settings.settings_json:
            return
        try:
            extra = json.loads(settings.settings_json)
        except (json.JSONDecodeError, TypeError):
            return

        permissions = extra.get("permissions")
        if not permissions:
            return

        claude_dir = os.path.join(work_dir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        settings_path = os.path.join(claude_dir, "settings.json")
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(permissions, f, ensure_ascii=False, indent=2)
        logger.info(f"Written .claude/settings.json to {settings_path}")
