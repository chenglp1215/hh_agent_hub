import asyncio
import json
import os
import shlex
import tempfile
from typing import Dict, Any, List

from loguru import logger

from core.session_manager import session_manager


class DockerReasonixRunner:
    """Reasonix (DeepSeek) executor that runs in an isolated Docker container.

    Uses asyncio.subprocess to run docker commands.
    User input is passed via stdin pipe.
    """

    IMAGE = os.environ.get("REASONIX_IMAGE", "hh-reasonix:latest")
    NETWORK = os.environ.get("DOCKER_NETWORK", "hh_agent_hub_agent-net")
    WORKSPACE_BASE = os.environ.get("WORKSPACE_BASE", "/data/workflow_workspaces")
    WORKSPACE_HOST_PATH = os.environ.get("WORKSPACE_HOST_PATH", "")

    def _to_host_path(self, container_path: str) -> str:
        """Convert worker container path to host path for Docker volume mounts."""
        if self.WORKSPACE_HOST_PATH and container_path.startswith(self.WORKSPACE_BASE):
            return container_path.replace(self.WORKSPACE_BASE, self.WORKSPACE_HOST_PATH, 1)
        return container_path

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
    # Docker execution (subprocess + stdin pipe)
    # ------------------------------------------------------------------

    async def _run_docker(self, workspace_dir: str, user_input: str,
                          api_key: str, model: str,
                          timeout_seconds: int) -> str:
        """Execute reasonix CLI inside a disposable Docker container."""

        # Write reasonix config (API key) to temp dir
        config_dir = tempfile.mkdtemp(prefix="reasonix_cfg_")
        config_path = os.path.join(config_dir, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"apiKey": api_key}, f)

        # Write reasonix.toml with model config
        toml_content = f'[model]\nmodel = "{model}"\n'
        toml_path = os.path.join(workspace_dir, "reasonix.toml")
        with open(toml_path, "w", encoding="utf-8") as f:
            f.write(toml_content)

        host_workspace = self._to_host_path(workspace_dir)

        inner_cmd = 'reasonix run "$(cat)"'

        cmd = [
            "docker", "run", "--rm", "-i",
            "--network", self.NETWORK,
            "--user", "1001:1001",
            "-v", f"{host_workspace}:/workspace",
            "-v", f"{config_path}:/home/reasonixuser/.reasonix/config.json:ro",
            "-w", "/workspace",
            "--memory", "512m",
            "--cpus", "1.0",
            self.IMAGE,
            "sh", "-c", inner_cmd,
        ]

        logger.info(f"Docker Reasonix: image={self.IMAGE}, model={model}, "
                    f"cwd={host_workspace}, timeout={timeout_seconds}s")

        try:
            # Use shell pipe: echo "input" | docker run -i ...
            shell_cmd = f'{shlex.join(["echo", "-n", user_input])} | {shlex.join(cmd)}'

            docker_proc = await asyncio.create_subprocess_shell(
                shell_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                docker_proc.communicate(),
                timeout=timeout_seconds,
            )

            stderr_text = stderr.decode("utf-8", errors="replace")
            if stderr_text.strip():
                logger.debug(f"Docker stderr: {stderr_text[:500]}")

            if docker_proc.returncode != 0:
                logger.error(f"Docker container exited with code {docker_proc.returncode}: {stderr_text[:500]}")
                return f"Error: Reasonix container failed (exit {docker_proc.returncode}): {stderr_text[:500]}"

            output = stdout.decode("utf-8", errors="replace")
            try:
                result = json.loads(output)
                if isinstance(result, dict):
                    return result.get("result", result.get("output", json.dumps(result, ensure_ascii=False)))
                return str(result)
            except json.JSONDecodeError:
                return output.strip() if output.strip() else "Execution completed (no output)"

        except asyncio.TimeoutError:
            logger.error(f"Docker Reasonix timed out after {timeout_seconds}s")
            return f"Error: Reasonix execution timed out after {timeout_seconds} seconds"
        except FileNotFoundError:
            logger.error("Docker not found. Ensure Docker is installed and in PATH.")
            return "Error: Docker not available - cannot execute Reasonix agent"
        except Exception as e:
            logger.error(f"Docker Reasonix execution failed: {e}")
            return f"Error: Reasonix container execution failed - {e}"
        finally:
            try:
                os.unlink(config_path)
                os.rmdir(config_dir)
                os.unlink(toml_path)
            except OSError:
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
