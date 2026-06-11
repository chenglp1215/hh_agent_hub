import json
import os
import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from loguru import logger


class ExecutionTracer:
    """执行追踪器 — 每个工作流执行一个实例"""

    def __init__(self, execution_id: str, workspace_path: str):
        self.execution_id = execution_id
        self.workspace_path = workspace_path
        self.trace = {
            "execution_id": execution_id,
            "workflow_name": "",
            "status": "running",
            "started_at": None,
            "spans": [],
            "errors": [],
        }
        self._current_agent_span: Optional[Dict] = None
        self._span_counter = 0

    def start_execution(self, workflow_name: str, workflow_id: int = None, app_id: int = None):
        self.trace["started_at"] = self._now()
        self.trace["workflow_name"] = workflow_name
        self.trace["workflow_id"] = workflow_id
        self.trace["app_id"] = app_id
        self._flush()

    def start_agent(self, agent_name: str, agent_type: str, stage: int):
        span = {
            "span_id": f"span_agent_{stage}",
            "type": "agent",
            "agent_name": agent_name,
            "agent_type": agent_type,
            "stage": stage,
            "status": "running",
            "started_at": self._now(),
            "children": [],
        }
        self.trace["spans"].append(span)
        self._current_agent_span = span
        self._flush()

    def add_llm_span(self, model: str, provider: str, prompt: str,
                      response: str, input_tokens: int, output_tokens: int,
                      duration_ms: int, status: str = "success"):
        span = {
            "span_id": self._next_span_id(),
            "type": "llm_call",
            "model": model, "provider": provider,
            "prompt": prompt[:2000], "response": response[:2000],
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "duration_ms": duration_ms, "status": status,
        }
        if self._current_agent_span:
            self._current_agent_span["children"].append(span)
        self._flush()

    def add_tool_span(self, tool_name: str, mcp_server: str,
                       arguments: dict, result: str,
                       duration_ms: int, status: str = "success"):
        span = {
            "span_id": self._next_span_id(),
            "type": "tool_call",
            "tool_name": tool_name, "mcp_server": mcp_server,
            "arguments": arguments, "result": str(result)[:2000],
            "duration_ms": duration_ms, "status": status,
        }
        if self._current_agent_span:
            self._current_agent_span["children"].append(span)
        self._flush()

    def add_kb_span(self, query: str, kb_ids: list,
                     result_count: int, duration_ms: int):
        span = {
            "span_id": self._next_span_id(),
            "type": "knowledge_retrieval",
            "query": query, "kb_ids": kb_ids,
            "result_count": result_count,
            "duration_ms": duration_ms, "status": "success",
        }
        if self._current_agent_span:
            self._current_agent_span["children"].append(span)
        self._flush()

    def finish_agent(self, status: str, summary: str = ""):
        agent = self._current_agent_span
        if agent:
            agent["status"] = status
            agent["duration_ms"] = self._elapsed_ms(agent["started_at"])
            agent["summary"] = summary
            total_tokens = sum(
                c.get("input_tokens", 0) + c.get("output_tokens", 0)
                for c in agent.get("children", [])
            )
            agent["token_usage"] = total_tokens
        self._flush()

    def finish_execution(self, status: str):
        self.trace["status"] = status
        self.trace["completed_at"] = self._now()
        self.trace["total_duration_ms"] = self._elapsed_ms(self.trace["started_at"])
        self._flush()

    def _flush(self):
        """写入 trace.json 文件"""
        path = os.path.join(self.workspace_path, "trace.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.trace, f, ensure_ascii=False, indent=2)

    def _next_span_id(self) -> str:
        self._span_counter += 1
        return f"span_{self._span_counter}"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _elapsed_ms(self, start: str) -> int:
        if not start:
            return 0
        try:
            start_dt = datetime.fromisoformat(start)
            return int((datetime.now(timezone.utc) - start_dt).total_seconds() * 1000)
        except Exception:
            return 0
