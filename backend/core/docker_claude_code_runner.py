import asyncio
import json
import os
import tempfile
from typing import Dict, Any, List

import docker
from loguru import logger

from core.session_manager import session_manager


class DockerClaudeCodeRunner:
    """Claude Code executor that runs in an isolated Docker container.

    Uses Docker SDK (docker-py) to manage containers via the Docker socket.
    """

    IMAGE = os.environ.get("CLAUDECODE_IMAGE", "hh-claudecode:latest")
    NETWORK = os.environ.get("DOCKER_NETWORK", "hh_agent_hub_agent-net")

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
                     context: Dict[str, Any] = None) -> str:
        context = context or {}

        has_registry_refs = (
            self.config.get("project_registry_id") and
            self.config.get("settings_registry_id")
        )

        if has_registry_refs:
            return await self._invoke_with_registries(user_input, session_id, context)
        else:
            return await self._invoke_legacy(user_input, session_id, context)

    # ------------------------------------------------------------------
    # Registry mode
    # ------------------------------------------------------------------

    async def _invoke_with_registries(self, user_input: str, session_id: str,
                                       context: Dict[str, Any]) -> str:
        from models.project_registry import ProjectRegistry
        from models.claude_settings import ClaudeSettingsRegistry

        project_registry_id = self.config.get("project_registry_id")
        settings_registry_id = self.config.get("settings_registry_id")

        project = await ProjectRegistry.get_or_none(id=project_registry_id)
        settings = await ClaudeSettingsRegistry.get_or_none(id=settings_registry_id)

        if not project:
            logger.error(f"ProjectRegistry id={project_registry_id} not found for agent {self.agent_name}")
            return f"Error: Project config not found (id={project_registry_id})"

        if not settings:
            logger.error(f"ClaudeSettingsRegistry id={settings_registry_id} not found for agent {self.agent_name}")
            return f"Error: Claude settings not found (id={settings_registry_id})"

        session_workspace = (context or {}).get("session_workspace", "")
        if not session_workspace:
            logger.warning(f"No session_workspace in context for agent {self.agent_name}")
            return "Error: No session workspace available"

        project_code_path = session_manager.get_project_code_path(session_id, project.name)
        session_manager.ensure_agent_workspace(session_id, self.agent_name)

        from core.git_ops import ensure_code_exists
        force_pull = self._needs_code_pull(context)
        ensure_code_exists(project, project_code_path, force_pull=force_pull)

        self._write_claude_md(session_workspace, context, project.system_prompt,
                              project_code_path=project_code_path)
        self._write_claude_settings(session_workspace, settings)

        model = settings.model or "claude-sonnet-4-6"
        max_turns = settings.max_turns or 25
        permission_mode = settings.permission_mode or "acceptEdits"

        extra_settings = {}
        if settings.settings_json and settings.settings_json.strip():
            try:
                extra_settings = json.loads(settings.settings_json)
            except json.JSONDecodeError:
                pass

        env_vars = extra_settings.get("env", {})
        env_model = env_vars.get("ANTHROPIC_MODEL")
        if env_model:
            model = env_model
        elif extra_settings.get("model"):
            model = extra_settings["model"]

        timeout_seconds = (project.fix_timeout_minutes or 30) * 60

        return await self._run_docker(
            workspace_dir=session_workspace,
            user_input=user_input,
            model=model,
            max_turns=max_turns,
            permission_mode=permission_mode,
            timeout_seconds=timeout_seconds,
            env_vars=env_vars,
        )

    def _needs_code_pull(self, context: Dict[str, Any]) -> bool:
        prompts_to_check = [self.system_prompt, context.get("system_prompt", "")]
        code_keywords = ["修改代码", "修复", "新增功能", "编写", "改代码",
                         "create", "modify", "fix", "implement", "write code"]
        for prompt in prompts_to_check:
            if any(kw in prompt for kw in code_keywords):
                return True
        return False

    # ------------------------------------------------------------------
    # Legacy mode
    # ------------------------------------------------------------------

    async def _invoke_legacy(self, user_input: str, session_id: str,
                              context: Dict[str, Any]) -> str:
        session_workspace = (context or {}).get("session_workspace", "")

        settings_json = self.config.get("settings_json", "")
        model = self.config.get("model", "claude-sonnet-4-6")
        max_turns = self.config.get("max_turns", 25)
        permission_mode = self.config.get("permission_mode", "acceptEdits")

        if session_workspace and session_id:
            work_dir = session_manager.ensure_agent_workspace(session_id, self.agent_name)
        else:
            work_dir = self.config.get("work_dir", os.getcwd())

        claude_dir = os.path.join(work_dir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        if settings_json and settings_json.strip():
            try:
                json.loads(settings_json)
                with open(os.path.join(claude_dir, "settings.json"), "w", encoding="utf-8") as f:
                    f.write(settings_json)
            except json.JSONDecodeError:
                pass

        self._write_claude_md(work_dir, context)

        cwd = session_workspace if session_workspace else work_dir
        timeout_seconds = max_turns * 15

        env_vars = {}
        if settings_json and settings_json.strip():
            try:
                extra = json.loads(settings_json)
                env_vars = extra.get("env", {})
            except json.JSONDecodeError:
                pass

        return await self._run_docker(
            workspace_dir=cwd,
            user_input=user_input,
            model=model,
            max_turns=max_turns,
            permission_mode=permission_mode,
            timeout_seconds=timeout_seconds,
            env_vars=env_vars,
        )

    # ------------------------------------------------------------------
    # Docker execution (SDK)
    # ------------------------------------------------------------------

    async def _run_docker(self, workspace_dir: str, user_input: str,
                          model: str, max_turns: int, permission_mode: str,
                          timeout_seconds: int,
                          env_vars: Dict[str, str] = None) -> str:
        """Execute claude CLI inside a disposable Docker container via Docker SDK."""

        # Write user_input to a temp file, mount into container
        fd, input_path = tempfile.mkstemp(suffix=".txt", prefix="claude_input_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(user_input)

            # Build the claude command
            claude_cmd = (
                f'claude --print --output-format json'
                f' --model {model}'
                f' --max-turns {max_turns}'
                f' --permission-mode {permission_mode}'
                f' --dangerously-skip-permissions'
                f' -p "$(cat /tmp/user_input.txt)"'
            )

            env_list = []
            if env_vars:
                env_list = [f"{k}={v}" for k, v in env_vars.items()]

            logger.info(f"Docker Claude Code: image={self.IMAGE}, model={model}, "
                        f"max_turns={max_turns}, cwd={workspace_dir}, timeout={timeout_seconds}s")

            result_text = await asyncio.wait_for(
                asyncio.to_thread(
                    self._docker_run,
                    workspace_dir, input_path, claude_cmd, env_list, timeout_seconds,
                ),
                timeout=timeout_seconds + 30,
            )
            return result_text

        except asyncio.TimeoutError:
            logger.error(f"Docker Claude Code timed out after {timeout_seconds}s")
            return f"Error: Claude Code execution timed out after {timeout_seconds} seconds"
        except Exception as e:
            logger.error(f"Docker Claude Code execution failed: {e}")
            return f"Error: Claude Code container execution failed - {e}"
        finally:
            try:
                os.unlink(input_path)
            except OSError:
                pass

    def _docker_run(self, workspace_dir: str, input_path: str,
                    claude_cmd: str, env_list: list, timeout_seconds: int) -> str:
        """Synchronous Docker SDK call — runs in thread pool."""
        client = docker.from_env()
        container = None
        try:
            container = client.containers.run(
                image=self.IMAGE,
                command=["sh", "-c", claude_cmd],
                network=self.NETWORK,
                volumes={
                    workspace_dir: {"bind": "/workspace", "mode": "rw"},
                    input_path: {"bind": "/tmp/user_input.txt", "mode": "ro"},
                },
                working_dir="/workspace",
                environment=env_list or None,
                mem_limit="512m",
                nano_cpus=1_000_000_000,  # 1 CPU
                detach=True,
                remove=True,
                stop_timeout=10,
                user="1001:1001",
            )

            # Wait for completion
            result = container.wait(timeout=timeout_seconds)
            exit_code = result.get("StatusCode", -1)

            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

            if stderr.strip():
                logger.debug(f"Docker stderr: {stderr[:500]}")

            if exit_code != 0:
                logger.error(f"Docker container exited with code {exit_code}: {stderr[:500]}")
                return f"Error: Claude Code container failed (exit {exit_code}): {stderr[:500]}"

            try:
                parsed = json.loads(stdout)
                if isinstance(parsed, dict):
                    return parsed.get("result", parsed.get("output", json.dumps(parsed, ensure_ascii=False)))
                return str(parsed)
            except json.JSONDecodeError:
                return stdout.strip() if stdout.strip() else "Execution completed (no output)"

        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # CLAUDE.md writer
    # ------------------------------------------------------------------

    def _write_claude_md(self, work_dir: str, context: Dict[str, Any] = None,
                          extra_system_prompt: str = None,
                          project_code_path: str = None) -> None:
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
        logger.info(f"Written CLAUDE.md to {claude_md_path}")

    def _write_claude_settings(self, work_dir: str, settings) -> None:
        """将 settings_json 原样写入 .claude/settings.json"""
        if not settings.settings_json:
            return
        claude_dir = os.path.join(work_dir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        settings_path = os.path.join(claude_dir, "settings.json")
        with open(settings_path, "w", encoding="utf-8") as f:
            f.write(settings.settings_json)
        logger.info(f"Written .claude/settings.json to {settings_path}")
