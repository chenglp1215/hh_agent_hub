import asyncio
import json
import os
import tempfile
from typing import Dict, Any, List

import docker
from loguru import logger

from core.session_manager import session_manager


class DockerReasonixRunner:
    """Reasonix (DeepSeek) executor that runs in an isolated Docker container.

    Uses Docker SDK (docker-py) to manage containers via the Docker socket.
    """

    IMAGE = os.environ.get("REASONIX_IMAGE", "hh-reasonix:latest")
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

        has_registry_ref = self.config.get("project_registry_id")

        if has_registry_ref:
            return await self._invoke_with_registry(user_input, session_id, context)
        else:
            return await self._invoke_legacy(user_input, session_id, context)

    # ------------------------------------------------------------------
    # Registry mode
    # ------------------------------------------------------------------

    async def _invoke_with_registry(self, user_input: str, session_id: str,
                                     context: Dict[str, Any]) -> str:
        from models.project_registry import ProjectRegistry

        project_registry_id = self.config.get("project_registry_id")
        project = await ProjectRegistry.get_or_none(id=project_registry_id)

        if not project:
            logger.error(f"ProjectRegistry id={project_registry_id} not found for agent {self.agent_name}")
            return f"Error: Project config not found (id={project_registry_id})"

        session_workspace = (context or {}).get("session_workspace", "")
        if not session_workspace:
            logger.warning(f"No session_workspace in context for agent {self.agent_name}")
            return "Error: No session workspace available"

        project_code_path = session_manager.get_project_code_path(session_id, project.name)
        session_manager.ensure_agent_workspace(session_id, self.agent_name)

        from core.git_ops import ensure_code_exists
        ensure_code_exists(project, project_code_path)

        self._write_project_instructions(session_workspace, context, project.system_prompt)

        api_key = self.config.get("deepseek_api_key", "")
        model = self.config.get("deepseek_model", "deepseek-chat")
        timeout_seconds = (project.fix_timeout_minutes or 30) * 60

        if not api_key:
            return "Error: DeepSeek API key not configured"

        return await self._run_docker(
            workspace_dir=session_workspace,
            user_input=user_input,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
        )

    # ------------------------------------------------------------------
    # Legacy mode
    # ------------------------------------------------------------------

    async def _invoke_legacy(self, user_input: str, session_id: str,
                              context: Dict[str, Any]) -> str:
        session_workspace = (context or {}).get("session_workspace", "")

        api_key = self.config.get("deepseek_api_key", "")
        model = self.config.get("deepseek_model", "deepseek-chat")
        max_turns = self.config.get("max_turns", 25)

        if not api_key:
            return "Error: DeepSeek API key not configured"

        if session_workspace and session_id:
            work_dir = session_manager.ensure_agent_workspace(session_id, self.agent_name)
        else:
            work_dir = self.config.get("work_dir", os.getcwd())

        self._write_project_instructions(work_dir, context)

        cwd = session_workspace if session_workspace else work_dir
        timeout_seconds = max_turns * 15

        return await self._run_docker(
            workspace_dir=cwd,
            user_input=user_input,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
        )

    # ------------------------------------------------------------------
    # Docker execution (SDK)
    # ------------------------------------------------------------------

    async def _run_docker(self, workspace_dir: str, user_input: str,
                          api_key: str, model: str,
                          timeout_seconds: int) -> str:
        """Execute reasonix CLI inside a disposable Docker container via Docker SDK."""

        # Write reasonix config (API key)
        config_dir = tempfile.mkdtemp(prefix="reasonix_cfg_")
        config_path = os.path.join(config_dir, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"apiKey": api_key}, f)

        # Write reasonix.toml with model config
        toml_content = f'[model]\nmodel = "{model}"\n'
        toml_path = os.path.join(workspace_dir, "reasonix.toml")
        with open(toml_path, "w", encoding="utf-8") as f:
            f.write(toml_content)

        # Write user_input to temp file
        fd, input_path = tempfile.mkstemp(suffix=".txt", prefix="reasonix_input_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(user_input)

            reasonix_cmd = 'reasonix run "$(cat /tmp/user_input.txt)"'

            logger.info(f"Docker Reasonix: image={self.IMAGE}, model={model}, "
                        f"cwd={workspace_dir}, timeout={timeout_seconds}s")

            result_text = await asyncio.wait_for(
                asyncio.to_thread(
                    self._docker_run,
                    workspace_dir, input_path, config_path, reasonix_cmd, timeout_seconds,
                ),
                timeout=timeout_seconds + 30,
            )
            return result_text

        except asyncio.TimeoutError:
            logger.error(f"Docker Reasonix timed out after {timeout_seconds}s")
            return f"Error: Reasonix execution timed out after {timeout_seconds} seconds"
        except Exception as e:
            logger.error(f"Docker Reasonix execution failed: {e}")
            return f"Error: Reasonix container execution failed - {e}"
        finally:
            try:
                os.unlink(input_path)
                os.unlink(config_path)
                os.rmdir(config_dir)
            except OSError:
                pass

    def _docker_run(self, workspace_dir: str, input_path: str,
                    config_path: str, reasonix_cmd: str, timeout_seconds: int) -> str:
        """Synchronous Docker SDK call — runs in thread pool."""
        client = docker.from_env()
        container = None
        try:
            container = client.containers.run(
                image=self.IMAGE,
                command=["sh", "-c", reasonix_cmd],
                network=self.NETWORK,
                volumes={
                    workspace_dir: {"bind": "/workspace", "mode": "rw"},
                    input_path: {"bind": "/tmp/user_input.txt", "mode": "ro"},
                    config_path: {"bind": "/home/reasonixuser/.reasonix/config.json", "mode": "ro"},
                },
                working_dir="/workspace",
                mem_limit="512m",
                nano_cpus=1_000_000_000,
                detach=True,
                remove=True,
                stop_timeout=10,
                user="1001:1001",
            )

            result = container.wait(timeout=timeout_seconds)
            exit_code = result.get("StatusCode", -1)

            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

            if stderr.strip():
                logger.debug(f"Docker stderr: {stderr[:500]}")

            if exit_code != 0:
                logger.error(f"Docker container exited with code {exit_code}: {stderr[:500]}")
                return f"Error: Reasonix container failed (exit {exit_code}): {stderr[:500]}"

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
    # Project instructions writer
    # ------------------------------------------------------------------

    def _write_project_instructions(self, work_dir: str, context: Dict[str, Any] = None,
                                     extra_system_prompt: str = None) -> None:
        context = context or {}
        os.makedirs(work_dir, exist_ok=True)

        parts = []

        system_prompt = context.get("system_prompt", "")
        if system_prompt:
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

        if parts:
            content = "\n".join(parts)
            instructions_path = os.path.join(work_dir, "INSTRUCTIONS.md")
            with open(instructions_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Written INSTRUCTIONS.md to {instructions_path}")
