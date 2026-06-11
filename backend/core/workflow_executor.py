import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class WorkflowTimeoutConfig:
    agent_timeout_seconds: int = 60
    workflow_timeout_seconds: int = 300
    retry_count: int = 2
    retry_delay_seconds: int = 3


class WorkflowExecutor:
    """带错误处理的工作流执行器"""

    def __init__(self, config: WorkflowTimeoutConfig = None):
        self.config = config or WorkflowTimeoutConfig()
        self.error_log: list = []

    async def execute_with_timeout(self, agent_fn, state: Dict[str, Any],
                                    agent_name: str) -> Dict[str, Any]:
        """带超时的 Agent 执行"""
        try:
            result = await asyncio.wait_for(
                agent_fn(state),
                timeout=self.config.agent_timeout_seconds,
            )
            return {"success": True, "result": result, "agent": agent_name}
        except asyncio.TimeoutError:
            self.error_log.append({
                "agent": agent_name, "error": "timeout",
                "message": f"超过 {self.config.agent_timeout_seconds}s 限制",
            })
            return {"success": False, "error": "timeout", "agent": agent_name}
        except Exception as e:
            self.error_log.append({"agent": agent_name, "error": str(e)})
            return {"success": False, "error": str(e), "agent": agent_name}

    async def execute_with_retry(self, agent_fn, state: Dict[str, Any],
                                  agent_name: str) -> Dict[str, Any]:
        """带重试的 Agent 执行"""
        last_error = None
        for attempt in range(self.config.retry_count + 1):
            result = await self.execute_with_timeout(agent_fn, state, agent_name)
            if result["success"]:
                result["retry_attempt"] = attempt
                return result
            last_error = result
            if attempt < self.config.retry_count:
                logger.warning(f"Retrying {agent_name} ({attempt + 1}/{self.config.retry_count})")
                await asyncio.sleep(self.config.retry_delay_seconds)
        last_error["retry_exhausted"] = True
        return last_error

    async def execute_workflow(self, compiled_graph, initial_state: Dict[str, Any],
                                error_strategy: str = "fail_fast") -> Dict[str, Any]:
        """执行编译后的工作流（带整体超时控制）"""
        try:
            result = await asyncio.wait_for(
                compiled_graph.ainvoke(initial_state),
                timeout=self.config.workflow_timeout_seconds,
            )
            return {"success": True, "result": result}
        except asyncio.TimeoutError:
            logger.error(f"Workflow timed out after {self.config.workflow_timeout_seconds}s")
            return {
                "success": False,
                "error": "workflow_timeout",
                "intermediate_results": initial_state.get("intermediate_results", {}),
            }
        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            if error_strategy == "skip_continue":
                return {
                    "success": True,
                    "partial": True,
                    "result": initial_state,
                    "errors": self.error_log,
                }
            return {
                "success": False,
                "error": str(e),
                "intermediate_results": initial_state.get("intermediate_results", {}),
                "error_log": self.error_log,
            }
