import json
import os
from typing import Dict, Any, List, Optional

from loguru import logger


class ClaudeCodeRunner:
    """Claude Code executor supporting two modes:

    1. New mode (registry references): claudecode_config = {"project_registry_id": int, "settings_registry_id": int}
       Queries registries for Git info and execution config, uses claude-code-sdk.

    2. Legacy mode (inline config): Uses config fields like settings_json, model, work_dir directly.
       Falls back to CLI subprocess for backward compatibility.
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
        """Execute a Claude Code task.

        Args:
            user_input: Task description from the user
            session_id: Session identifier
            context: Additional context including system_prompt, intermediate_results

        Returns:
            Claude Code execution result text
        """
        context = context or {}

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

        try:
            from core.git_ops import clone_or_pull_repo
            clone_or_pull_repo(project)
        except Exception as e:
            logger.error(f"Git clone failed for project {project.name}: {e}")
            return f"Error: Git clone failed - {e}"

        workspace_dir = str(await self._get_workspace_dir(project))
        self._write_claude_md(workspace_dir, context, project.system_prompt)

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
            return f"Error: Claude Code execution failed - {e}"

    async def _get_workspace_dir(self, project) -> str:
        from core.git_ops import get_workspace_path
        return str(get_workspace_path(project))

    async def _run_sdk(self, workspace_dir: str, user_input: str,
                        settings, project, context: Dict[str, Any]) -> str:
        """Execute Claude Code using claude-code-sdk."""
        from claude_code_sdk import ClaudeSDKClient, ClaudeCodeOptions
        from claude_code_sdk.types import (
            ResultMessage, AssistantMessage, TextBlock, ToolUseBlock,
        )

        options_kwargs = {
            "permission_mode": settings.permission_mode,
            "cwd": workspace_dir,
            "max_turns": settings.max_turns,
        }

        extra_settings = {}
        if settings.settings_json and settings.settings_json.strip():
            try:
                extra_settings = json.loads(settings.settings_json)
            except json.JSONDecodeError:
                pass

        if extra_settings.get("model"):
            options_kwargs["model"] = extra_settings["model"]
        elif settings.model:
            options_kwargs["model"] = settings.model

        env_vars = extra_settings.get("env", {})
        if env_vars:
            for k, v in env_vars.items():
                os.environ[k] = v
            logger.info(f"Loaded {len(env_vars)} env vars from settings_json")

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
                            return f"Claude Code execution error: {result}"

                        logger.info(f"Claude Code completed: cost={getattr(message, 'total_cost_usd', 'N/A')}")
                        return result or last_text or "Execution completed (no output)"

                if got_result:
                    break

                if tool_results and any(t.get("type") == "question" for t in tool_results):
                    return json.dumps({"questions": tool_results}, ensure_ascii=False)
                else:
                    break

            return last_text or "Execution completed (no output)"

        except Exception as e:
            logger.error(f"SDK execution error: {e}")
            raise
        finally:
            await client.disconnect()

    async def _run_cli_legacy(self, workspace_dir: str, user_input: str,
                               settings) -> str:
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
            return "Error: Claude Code execution timed out"

    async def _invoke_legacy(self, user_input: str, session_id: str,
                              context: Dict[str, Any]) -> str:
        """Legacy mode: use inline config fields for backward compatibility."""
        import asyncio

        settings_json = self.config.get("settings_json", "")
        model = self.config.get("model", "claude-sonnet-4-6")
        max_turns = self.config.get("max_turns", 25)
        work_dir = self.config.get("work_dir", "")
        permission_mode = self.config.get("permission_mode", "acceptEdits")

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

        system_prompt = context.get("system_prompt", "")
        if system_prompt:
            parts.append("")
            parts.append("## System Instructions")
            parts.append(system_prompt)
        if extra_system_prompt:
            parts.append("")
            parts.append("## Project Instructions")
            parts.append(extra_system_prompt)

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
