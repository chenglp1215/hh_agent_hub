import asyncio
from typing import List, Dict, Any
from loguru import logger


async def execute_parallel_group(
    agents: List[tuple],
    state: Dict[str, Any],
    timeout: int = 120,
) -> Dict[str, Any]:
    """并行执行一组 Agent"""
    tasks = []
    for agent_name, node_fn in agents:
        async def run_agent(name, fn, st):
            try:
                result = await fn(st)
                return name, {"status": "success", "result": result}
            except Exception as e:
                return name, {"status": "error", "error": str(e)}

        task = asyncio.create_task(run_agent(agent_name, node_fn, state))
        task.agent_name = agent_name
        tasks.append(task)

    done, pending = await asyncio.wait(tasks, timeout=timeout)

    results = {}
    for task in done:
        name, result = task.result()
        results[name] = result

    for task in pending:
        task.cancel()
        results[task.agent_name] = {"status": "timeout", "error": "timeout"}

    logger.info(f"Parallel group: {len(done)} completed, {len(pending)} timed out")
    return {"parallel_results": results}


def merge_parallel_results(results: Dict[str, Any],
                           merge_strategy: str = "concat") -> str:
    """合并并行 Agent 的执行结果"""
    outputs = []
    for name, result in results.items():
        if isinstance(result, dict):
            content = result.get("result", {})
            if isinstance(content, dict):
                agent_output = content.get("intermediate_results", {}).get(name, "")
            else:
                agent_output = str(content)
        else:
            agent_output = str(result)

        if agent_output:
            outputs.append(f"[{name}]: {agent_output}")

    if merge_strategy == "concat":
        return "\n\n".join(outputs)
    elif merge_strategy == "first":
        return outputs[0] if outputs else ""
    else:
        return "\n\n".join(outputs)
