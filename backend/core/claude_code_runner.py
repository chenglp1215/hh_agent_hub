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
        raw_work_dir = config.get("work_dir", "")
        self.work_dir = raw_work_dir if raw_work_dir else os.getcwd()
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
