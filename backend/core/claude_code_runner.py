import asyncio
import json
import os
import tempfile
from typing import Dict, Any
from loguru import logger


class ClaudeCodeRunner:
    """Claude Code CLI 执行器 — 通过子进程调用 Claude Code"""

    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        self.work_dir = config.get("work_dir", os.getcwd())
        self.model = config.get("model", "claude-sonnet-4-6")
        self.max_turns = config.get("max_turns", 25)
        self.permission_mode = config.get("permission_mode", "acceptEdits")
        self.claude_md_path = config.get("claude_md_path", "")
        self.allowed_tools = config.get("allowed_tools", [])
        self.extra_args = config.get("extra_args", [])
        self.env = config.get("env", {})

    async def invoke(self, user_input: str, session_id: str,
                     context: Dict[str, Any] = None) -> str:
        """通过 CLI 执行 Claude Code 任务"""
        context = context or {}

        # 构建临时 CLAUDE.md 内容
        claude_md_content = self._build_claude_md(context)
        claude_md_path = self._write_temp_claude_md(claude_md_content, session_id)

        # 构建命令
        cmd = [
            "claude",
            "--model", self.model,
            "--max-turns", str(self.max_turns),
            "--permission-mode", self.permission_mode,
            "--print",
            "--output-format", "json",
        ]

        if claude_md_path:
            cmd.extend(["--custom-instructions", claude_md_path])

        if self.allowed_tools:
            cmd.extend(["--allowed-tools", ",".join(self.allowed_tools)])

        if self.extra_args:
            cmd.extend(self.extra_args)

        logger.info(f"Claude Code CLI: model={self.model}, max_turns={self.max_turns}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.work_dir,
                env={**os.environ, **self.env},
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

    def _build_claude_md(self, context: Dict[str, Any]) -> str:
        """构建 CLAUDE.md 内容"""
        parts = []
        if context.get("system_prompt"):
            parts.append(context["system_prompt"])
        if context.get("intermediate_results"):
            parts.append(
                "\n## 上游结果\n"
                + json.dumps(context["intermediate_results"], ensure_ascii=False, indent=2)
            )
        return "\n".join(parts)

    def _write_temp_claude_md(self, content: str, session_id: str) -> str:
        """写入临时 CLAUDE.md 文件"""
        if not content:
            return self.claude_md_path or ""
        tmp_dir = tempfile.mkdtemp(prefix=f"claude_md_{session_id}_")
        path = os.path.join(tmp_dir, "CLAUDE.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
