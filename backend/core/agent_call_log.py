"""Agent 调用详细日志记录器

三层日志级别（由 AGENT_LOG_LEVEL 环境变量控制）：
- basic:   只记录元数据（agent名、类型、输入/输出长度、耗时）-- 向后兼容
- verbose: 截断内容到 stderr（Docker可见），完整内容写入 logs/agent_calls_detail.log
- full:    完整内容到 stderr + 文件

截断阈值：
- system_prompt: 5000 字符
- input/output: 10000 字符
"""

import json
import os
import sys
import uuid
import threading
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger

# 从文件路径计算项目根目录: backend/core/agent_call_log.py -> project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AgentCallLogger:
    """Agent 调用日志记录器 — 模块级单例使用"""

    TRUNCATE_SYSTEM_PROMPT = 5000
    TRUNCATE_INPUT_OUTPUT = 10000
    MAX_LOG_FILE_BYTES = 100 * 1024 * 1024  # 100MB
    MAX_LOG_FILES = 5

    def __init__(self):
        self._level = os.environ.get("AGENT_LOG_LEVEL", "verbose").lower()
        # 详细日志文件路径
        self._detail_log_path = os.environ.get(
            "AGENT_CALL_LOG_FILE",
            os.path.join(_PROJECT_ROOT, "logs", "agent_calls_detail.log"),
        )
        # 确保日志目录存在
        log_dir = os.path.dirname(self._detail_log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        # 线程锁保护并发文件写入（多进程场景下仍受限，但可防止同一进程内线程交错）
        self._write_lock = threading.Lock()
        logger.info(
            f"[AgentCallLogger] initialized, level={self._level}, "
            f"detail_log={self._detail_log_path}"
        )

    @property
    def level(self) -> str:
        return self._level

    # ------------------------------------------------------------------
    # ID 生成
    # ------------------------------------------------------------------

    def start_trace(self) -> str:
        """生成一个新的 trace ID（每次工作流执行一个）"""
        return str(uuid.uuid4())

    def start_span(self, parent_span_id: Optional[str] = None) -> str:
        """生成一个新的 span ID（每次 agent 调用一个）"""
        return str(uuid.uuid4())

    # ------------------------------------------------------------------
    # 统一记录入口
    # ------------------------------------------------------------------

    def log_agent_call(
        self,
        trace_id: str,
        parent_span_id: Optional[str],
        span_id: str,
        agent_name: str,
        agent_type: str,
        system_prompt: str = "",
        user_input: str = "",
        output: str = "",
        duration_ms: int = 0,
        token_usage: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """统一记录一次 Agent 调用

        Args:
            trace_id: 追踪 ID（工作流级别）
            parent_span_id: 父 span ID（调用者）
            span_id: 当前 span ID
            agent_name: Agent 名称
            agent_type: Agent 类型（local / claudecode / reasonix / supervisor / http）
            system_prompt: 完整 system prompt 内容
            user_input: 用户输入 / 任务描述
            output: Agent 输出
            duration_ms: 耗时（毫秒）
            token_usage: Token 用量字典 {input_tokens, output_tokens, total_tokens, model_name}
            metadata: 额外元数据（如路由决策、round 等）
        """
        token_usage = token_usage or {}
        metadata = metadata or {}

        # 构建 JSON 记录
        record: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "trace_id": trace_id,
            "parent_span_id": parent_span_id,
            "span_id": span_id,
            "agent_name": agent_name,
            "agent_type": agent_type,
            "system_prompt_len": len(system_prompt),
            "user_input_len": len(user_input),
            "output_len": len(output),
            "duration_ms": duration_ms,
            "token_usage": token_usage,
            "metadata": metadata,
        }

        if self._level == "basic":
            # 仅元数据到 stderr
            self._log_stderr(
                agent_name,
                f"[BASIC] type={agent_type}, sys_prompt_len={len(system_prompt)}, "
                f"input_len={len(user_input)}, output_len={len(output)}, "
                f"duration={duration_ms}ms",
            )
            # 完整 JSON（不含内容）到文件
            self._write_detail(record)
            return

        # verbose / full 模式：包含内容
        record["system_prompt"] = system_prompt
        record["user_input"] = user_input
        record["output"] = output

        if self._level == "verbose":
            # 截断内容到 stderr，完整内容到文件
            sp = system_prompt
            if len(sp) > self.TRUNCATE_SYSTEM_PROMPT:
                sp = sp[: self.TRUNCATE_SYSTEM_PROMPT] + "\n... [truncated]"
            inp = user_input
            if len(inp) > self.TRUNCATE_INPUT_OUTPUT:
                inp = inp[: self.TRUNCATE_INPUT_OUTPUT] + "\n... [truncated]"
            out = output
            if len(out) > self.TRUNCATE_INPUT_OUTPUT:
                out = out[: self.TRUNCATE_INPUT_OUTPUT] + "\n... [truncated]"

            self._log_stderr(agent_name, f"SYSTEM_PROMPT=\n{sp}")
            self._log_stderr(agent_name, f"INPUT=\n{inp}")
            self._log_stderr(agent_name, f"OUTPUT=\n{out}")

            # 完整 JSON lines 到文件
            self._write_detail(record)

        elif self._level == "full":
            # 完整内容到 stderr + 文件
            self._log_stderr(agent_name, f"SYSTEM_PROMPT=\n{system_prompt}")
            self._log_stderr(agent_name, f"INPUT=\n{user_input}")
            self._log_stderr(agent_name, f"OUTPUT=\n{output}")
            self._write_detail(record)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _log_stderr(self, agent_name: str, message: str):
        """写入 stderr，Docker 日志中可见"""
        line = f"[AGENT: {agent_name}] {message}"
        print(line, file=sys.stderr, flush=True)

    def _write_detail(self, record: Dict[str, Any]):
        """以 JSON lines 格式写入详细日志文件

        线程安全（同一进程内），自动轮转（超 100MB 后归档）。
        同步写入（单行追加 <1ms），不会对事件循环造成可感知的阻塞。
        轮转操作（仅在 100MB 边界触发）同步执行，频率极低可接受。
        多进程场景（Docker replicas>1）建议配置不同的 AGENT_CALL_LOG_FILE 路径，
        或使用 loguru sink 替代自管理轮转。
        """
        try:
            with self._write_lock:
                self._rotate_if_needed()
                with open(self._detail_log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            logger.warning(f"[AgentCallLogger] Failed to write detail log: {e}")

    def _rotate_if_needed(self):
        """当日志文件超过 MAX_LOG_FILE_BYTES 时，重命名为 .1 / .2 ...
        保留 MAX_LOG_FILES 个历史文件。
        """
        if not os.path.exists(self._detail_log_path):
            return
        try:
            size = os.path.getsize(self._detail_log_path)
            if size < self.MAX_LOG_FILE_BYTES:
                return
            # 删除最旧的归档文件
            last_path = f"{self._detail_log_path}.{self.MAX_LOG_FILES}"
            if os.path.exists(last_path):
                os.remove(last_path)
            # 依次重命名 .4 -> .5, .3 -> .4, ..., .1 -> .2
            for i in range(self.MAX_LOG_FILES - 1, 0, -1):
                src = f"{self._detail_log_path}.{i}"
                dst = f"{self._detail_log_path}.{i + 1}"
                if os.path.exists(src):
                    os.rename(src, dst)
            # 重命名当前日志为 .1
            os.rename(self._detail_log_path, f"{self._detail_log_path}.1")
        except Exception as e:
            logger.warning(f"[AgentCallLogger] Log rotation failed: {e}")


# 模块级单例
agent_call_logger = AgentCallLogger()
