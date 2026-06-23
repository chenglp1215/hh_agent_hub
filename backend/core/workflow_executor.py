"""工作流执行器 — 在 worker 中重建并执行 LangGraph 工作流

数据流：
  1. worker 从 task_queue 拿到任务（app_id + session_id + message）
  2. 从 DB 加载 App → Workflow → Agents（含 MCP/Skill 关联）
  3. 构建 agent_nodes + workflow_config
  4. 编译 LangGraph
  5. 执行（ainvoke 或 astream）
  6. 结果回写 DB + 通过 task_queue 发布
"""

import asyncio
import os
import time as time_mod
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from models.app import App
from models.workflow import Workflow
from models.agent import Agent
from models.mcp_server import AgentMcpLink
from models.skill import AgentSkillLink
from models.session import Session
from core.workflow_engine import workflow_engine, AgentState
from core.agent_factory import agent_factory
from core.session_manager import session_manager
from core.task_queue import TaskQueue
from models.chat_log import ChatLog


async def build_workflow(session: Session, message: str) -> tuple:
    """从 DB 重建 LangGraph 工作流和初始状态（原 chat.py _build_agent_graph）

    Returns:
        (graph, initial_state, agent_names, flow_type)
        失败返回 (None, None, None, None)
    """
    messages = session.messages or []
    messages.append({"role": "user", "content": message})
    session.messages = messages
    await session.save()

    # Tortoise ORM: ForeignKey 需要 await 才能获取关联对象
    try:
        app_obj = await session.app
        workflow_id = app_obj.workflow_id
    except AttributeError:
        workflow_id = None

    workflow = await Workflow.get_or_none(id=workflow_id)
    if not workflow:
        logger.error(f"Workflow not found for app {session.app_id}")
        return None, None, None, None

    worker_ids = workflow.worker_agent_ids or []
    agent_nodes = {}
    agent_names = []
    worker_descriptions = {}

    for wid in worker_ids:
        agent = await Agent.get_or_none(id=wid)
        if not agent:
            continue
        mcp_links = await AgentMcpLink.filter(agent_id=agent.id).prefetch_related("mcp_server")
        skill_links = await AgentSkillLink.filter(agent_id=agent.id).prefetch_related("skill")
        config = {
            "name": agent.name, "agent_type": agent.agent_type, "role": agent.role,
            "llm_config": agent.llm_config, "llm_config_id": agent.llm_config_id,
            "http_config": agent.http_config, "claudecode_config": agent.claudecode_config,
            "a2a_config": agent.a2a_config,
            "system_prompt": agent.system_prompt,
            "knowledge_base_ids": agent.knowledge_base_ids or [],
            "mcp_servers": [{
                "id": ml.mcp_server.id, "name": ml.mcp_server.name,
                "base_url": ml.mcp_server.base_url, "headers": ml.mcp_server.headers,
                "single_endpoint": ml.mcp_server.single_endpoint,
                "enabled_tools": ml.enabled_tools, "enabled": ml.enabled,
            } for ml in mcp_links],
            "skills": [{
                "name": sl.skill.name, "skill_type": sl.skill.skill_type,
                "content": sl.skill.content,
            } for sl in skill_links],
        }
        node_fn = await agent_factory.create(config)
        agent_nodes[agent.name] = node_fn
        agent_names.append(agent.name)
        worker_descriptions[agent.name] = agent.description or ""

    wf_config: Dict[str, Any] = {
        "flow_type": workflow.flow_type,
        "worker_agent_ids": agent_names,
    }

    if workflow.flow_type == "supervisor" and workflow.supervisor_agent_id:
        sup_agent = await Agent.get_or_none(id=workflow.supervisor_agent_id)
        if sup_agent:
            mcp_links = await AgentMcpLink.filter(agent_id=sup_agent.id).prefetch_related("mcp_server")
            skill_links = await AgentSkillLink.filter(agent_id=sup_agent.id).prefetch_related("skill")
            wf_config["supervisor_agent_name"] = sup_agent.name
            sup_config = {
                "name": sup_agent.name, "agent_type": sup_agent.agent_type, "role": sup_agent.role,
                "llm_config": sup_agent.llm_config, "llm_config_id": sup_agent.llm_config_id,
                "system_prompt": sup_agent.system_prompt,
                "knowledge_base_ids": sup_agent.knowledge_base_ids or [],
                "mcp_servers": [{
                    "id": ml.mcp_server.id, "name": ml.mcp_server.name,
                    "base_url": ml.mcp_server.base_url, "headers": ml.mcp_server.headers,
                    "single_endpoint": ml.mcp_server.single_endpoint,
                    "enabled_tools": ml.enabled_tools, "enabled": ml.enabled,
                } for ml in mcp_links],
                "skills": [{
                    "name": sl.skill.name, "skill_type": sl.skill.skill_type,
                    "content": sl.skill.content,
                } for sl in skill_links],
                "_available_workers": agent_names,
                "_worker_descriptions": worker_descriptions,
            }
            sup_node_fn = await agent_factory.create(sup_config)
            agent_nodes[sup_agent.name] = sup_node_fn

    graph = await workflow_engine.build_workflow(wf_config, agent_nodes)
    initial_state: AgentState = {
        "user_input": message, "messages": messages,
        "current_agent": "", "next_agent": "",
        "intermediate_results": {}, "final_answer": "",
        "need_human": False, "human_input": "", "error": None, "trace": [],
        "session_id": session.id,
        "session_workspace": session.workspace_path or "",
    }
    return graph, initial_state, agent_names, workflow.flow_type


async def execute_task(task: Dict[str, Any], task_queue: TaskQueue):
    """worker 执行入口：重建工作流 → 执行 → 回写结果

    Args:
        task: 从队列取到的任务 dict
        task_queue: TaskQueue 实例（用于发布事件/结果）
    """
    task_id = task["task_id"]
    app_id = task["app_id"]
    session_id = task["session_id"]
    message = task["message"]
    stream = task.get("stream", False)

    start = time_mod.time()
    duration_ms = 0
    final_answer = ""
    agent_names = []
    trace_data = []
    error_message = None

    try:
        app = await App.get_or_none(id=app_id, enabled=True)
        if not app:
            raise ValueError(f"App {app_id} not found or disabled")

        # 获取/创建 session workspace
        session = await Session.get_or_none(id=session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if not session.workspace_path:
            ws = await session_manager.create_workspace(session_id)
            session.workspace_path = ws

        # 构建工作流图
        graph, initial_state, agent_names, flow_type = await build_workflow(session, message)
        if graph is None:
            raise ValueError("Failed to build workflow graph")

        if stream:
            # ── 流式执行 ──
            await task_queue.publish_event(task_id, "thinking", content="正在分析问题...")
            final_answer = ""
            seen_outputs = set()
            seen_routes = set()

            async for chunk in graph.astream(initial_state, stream_mode="updates"):
                for node_name, update in chunk.items():
                    intermediate = update.get("intermediate_results") or {}
                    trace = update.get("trace") or []

                    for t in trace:
                        if t.get("type") == "supervisor_route":
                            target = t.get("target", "end")
                            route_key = f"{t.get('round')}:{target}"
                            if target != "end" and route_key not in seen_routes:
                                seen_routes.add(route_key)
                                await task_queue.publish_event(
                                    task_id, "agent_call", agent=target
                                )

                    for agent_name, output in intermediate.items():
                        if agent_name.startswith("_"):
                            continue
                        output_str = str(output)
                        output_key = f"{agent_name}:{output_str[:50]}"
                        if output_key not in seen_outputs:
                            seen_outputs.add(output_key)
                            await task_queue.publish_event(
                                task_id, "agent_result",
                                agent=agent_name, output=output_str[:500],
                            )

                    for k, v in intermediate.items():
                        if not k.startswith("_"):
                            final_answer = str(v)

                    # 处理 supervisor 直接回复（如问候语短路），final_answer 在 update 而非 intermediate
                    direct_answer = update.get("final_answer")
                    if not final_answer and direct_answer:
                        final_answer = str(direct_answer)

            if final_answer:
                await task_queue.publish_event(task_id, "text", content=final_answer)

            duration_ms = int((time_mod.time() - start) * 1000)
            await task_queue.publish_event(
                task_id, "done",
                session_id=session_id, duration_ms=duration_ms,
            )

            # 更新 session 消息
            msg_list = (session.messages or [])[:]
            msg_list.append({"role": "assistant", "content": final_answer})
            session.messages = msg_list
            session.updated_at = datetime.now()
            await session.save()

            # 写入 ChatLog
            await _save_chat_log(app, session, task_id, message,
                                 final_answer, duration_ms, "success",
                                 agent_names=agent_names, trace_data=trace_data)

            # 写入结果
            await task_queue.publish_result(task_id, {
                "final_answer": final_answer,
                "duration_ms": duration_ms,
                "session_id": session_id,
            })

        else:
            # ── 非流式执行（触发器任务自动重试 LLM 风控误拦） ──
            max_retries = 2 if session_id.startswith("trigger_") else 0
            result = None
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    result = await graph.ainvoke(initial_state)
                    break
                except Exception as e:
                    err_str = str(e)
                    # 仅对 LLM 内容风控错误重试，其他错误直接抛出
                    if attempt < max_retries and ("risk" in err_str.lower() or "400" in err_str):
                        logger.warning(
                            f"Task {task_id} attempt {attempt + 1} failed (content moderation), "
                            f"retrying in 3s: {err_str[:200]}"
                        )
                        await asyncio.sleep(3)
                        last_error = e
                    else:
                        raise
            if result is None and last_error:
                raise last_error
            duration_ms = int((time_mod.time() - start) * 1000)

            final_answer = result.get("final_answer", "")
            if not final_answer:
                intermediate = result.get("intermediate_results", {})
                if intermediate:
                    last_key = list(intermediate.keys())[-1]
                    final_answer = intermediate.get(last_key, "")

            trace_data = result.get("trace", [])

            msg_list = (session.messages or [])[:]
            msg_list.append({"role": "assistant", "content": final_answer})
            session.messages = msg_list
            session.updated_at = datetime.now()
            await session.save()

            # 写入 ChatLog
            await _save_chat_log(app, session, task_id, message,
                                 final_answer, duration_ms, "success",
                                 agent_names=agent_names, trace_data=trace_data)

            # 更新 TriggerExecution 状态
            try:
                from models.trigger import TriggerExecution
                te = await TriggerExecution.filter(task_id=task_id).first()
                if te:
                    te.status = "success"
                    te.duration_ms = duration_ms
                    te.completed_at = datetime.now()
                    await te.save(update_fields=["status", "duration_ms", "completed_at"])
            except Exception as te_err:
                logger.warning(f"Failed to update TriggerExecution: {te_err}")

            await task_queue.publish_result(task_id, {
                "final_answer": final_answer,
                "intermediate_results": result.get("intermediate_results", {}),
                "duration_ms": duration_ms,
                "trace": trace_data,
                "session_id": session_id,
            })

            logger.info(f"Task {task_id} completed in {duration_ms}ms")

            # 写入 WorkflowTrace 记录（主控台 + 执行追踪页面数据来源）
            try:
                from models.workflow_trace import WorkflowTrace
                await WorkflowTrace.create(
                    execution_id=task_id,
                    workflow_id=workflow.id if workflow else None,
                    app_id=app_id,
                    status="success",
                    agent_count=len(agent_names),
                    total_duration_ms=duration_ms,
                    trace_file_path=os.path.join(
                        session.workspace_path or "", "trace.json"
                    ) if session.workspace_path else "",
                    started_at=datetime.fromtimestamp(start),
                    completed_at=datetime.now(),
                )
            except Exception as wt_err:
                logger.warning(f"Failed to create WorkflowTrace: {wt_err}")

            # 如果是触发器触发的任务，发送通知
            try:
                if session_id.startswith("trigger_"):
                    from models.trigger import Trigger, TriggerExecution
                    import re
                    m = re.match(r"trigger_(?:manual_)?(\d+)_", session_id)
                    if m:
                        trigger_id = int(m.group(1))
                        trigger = await Trigger.get_or_none(id=trigger_id).select_related("notification")
                        te = await TriggerExecution.filter(task_id=task_id).first()
                        if trigger and te:
                            from core.trigger_notifier import send_trigger_notification
                            import asyncio
                            asyncio.create_task(send_trigger_notification(trigger, te))
            except Exception as notify_err:
                logger.warning(f"Failed to send trigger notification: {notify_err}")

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        await task_queue.publish_result(task_id, {
            "error": str(e),
            "final_answer": f"执行出错: {str(e)}",
            "duration_ms": int((time_mod.time() - start) * 1000),
            "session_id": session_id,
        })
        # 出错时也写入 ChatLog
        try:
            session = await Session.get_or_none(id=session_id)
            app = await App.get_or_none(id=app_id) if app_id else None
            await _save_chat_log(app, session, task_id, message,
                                 final_answer, duration_ms, "error",
                                 agent_names=agent_names, trace_data=trace_data,
                                 error_message=str(e))

            # 更新 TriggerExecution 状态为失败
            try:
                from models.trigger import TriggerExecution
                te = await TriggerExecution.filter(task_id=task_id).first()
                if te:
                    te.status = "failed"
                    te.error_message = str(e)[:500]
                    te.duration_ms = int((time_mod.time() - start) * 1000)
                    te.completed_at = datetime.now()
                    await te.save(update_fields=["status", "error_message", "duration_ms", "completed_at"])
            except Exception as te_err:
                logger.warning(f"Failed to update TriggerExecution: {te_err}")

            # 写入 WorkflowTrace 记录（失败）
            try:
                from models.workflow_trace import WorkflowTrace
                await WorkflowTrace.create(
                    execution_id=task_id,
                    app_id=app_id,
                    status="failed",
                    agent_count=len(agent_names),
                    total_duration_ms=int((time_mod.time() - start) * 1000),
                    error_summary=str(e)[:500],
                    started_at=datetime.fromtimestamp(start),
                    completed_at=datetime.now(),
                )
            except Exception as wt_err:
                logger.warning(f"Failed to create WorkflowTrace: {wt_err}")

            # 如果是触发器触发的任务，发送失败通知
            try:
                if session_id.startswith("trigger_"):
                    from models.trigger import Trigger, TriggerExecution
                    import re
                    m = re.match(r"trigger_(?:manual_)?(\d+)_", session_id)
                    if m:
                        trigger_id = int(m.group(1))
                        trigger = await Trigger.get_or_none(id=trigger_id).select_related("notification")
                        te = await TriggerExecution.filter(task_id=task_id).first()
                        if trigger and te:
                            from core.trigger_notifier import send_trigger_notification
                            import asyncio
                            asyncio.create_task(send_trigger_notification(trigger, te))
            except Exception as notify_err:
                logger.warning(f"Failed to send trigger notification: {notify_err}")

        except Exception as log_err:
            logger.warning(f"Failed to save ChatLog: {log_err}")

        if stream:
            await task_queue.publish_event(task_id, "error", message=str(e))


async def _save_chat_log(app, session, task_id: str, user_input: str,
                          final_answer: str, duration_ms: int, status: str,
                          agent_names: List[str] = None,
                          trace_data: List[Dict] = None,
                          error_message: str = None):
    """将会话对话写入 ChatLog 表，同一 session 复用一条记录"""
    try:
        trace_summary = None
        if trace_data:
            trace_summary = [
                {k: v for k, v in t.items() if k in (
                    "type", "agent", "round", "target", "output_len", "elapsed_ms"
                )}
                for t in trace_data
            ]

        existing = await ChatLog.get_or_none(session=session)
        if existing:
            existing.user_input = (existing.user_input or "") + "\n---\n" + user_input
            existing.final_answer = (existing.final_answer or "") + "\n---\n" + final_answer
            existing.duration_ms = (existing.duration_ms or 0) + duration_ms
            existing.status = status if status == "error" else existing.status
            existing.agent_count = max(existing.agent_count or 0, len(agent_names or []))
            existing.trace_summary = trace_summary or existing.trace_summary
            existing.error_message = error_message or existing.error_message
            await existing.save()
        else:
            await ChatLog.create(
                app=app,
                session=session,
                task_id=task_id,
                user_input=user_input,
                final_answer=final_answer,
                duration_ms=duration_ms,
                status=status,
                error_message=error_message,
                agent_count=len(agent_names or []),
                trace_summary=trace_summary,
            )
    except Exception as e:
        logger.warning(f"Failed to save ChatLog: {e}")
