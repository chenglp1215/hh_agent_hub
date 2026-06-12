import uuid
import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from models.app import App
from models.workflow import Workflow
from models.session import Session
from schemas.chat import ChatRequest
from utils.response import success, error
from utils.sse import sse_event
from loguru import logger

router = APIRouter(prefix="/chat", tags=["对话"])


@router.post("")
async def chat(req: ChatRequest, request: Request):
    """Chat API 入口

    支持流式（SSE）和非流式两种响应模式。
    通过 ApiKeyMiddleware 完成应用认证，也可以通过 app_id 直接查找应用。

    Args:
        req: 聊天请求体，包含 app_id, message, stream 等字段
        request: FastAPI 请求对象，用于获取中间件设置的应用信息
    """
    app = getattr(request.state, "app", None)
    if not app:
        app = await App.get_or_none(id=req.app_id, enabled=True)
    if not app:
        return error(code=400, message="应用不存在或已禁用")

    session_id = req.session_id or str(uuid.uuid4())
    session = await Session.get_or_none(id=session_id)

    if not session:
        session = await Session.create(
            id=session_id,
            app=app,
            user_id="",
            messages=[],
            expired_at=datetime.now() + timedelta(hours=1),
        )

    if req.stream:
        return StreamingResponse(
            _stream_chat(session, req.message),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    result = await _execute_chat(session, req.message)
    return success(data={
        "session_id": session_id,
        "message": result.get("final_answer", ""),
        "intermediate_results": result.get("intermediate_results", {}),
        "duration_ms": result.get("duration_ms", 0),
        "trace": result.get("trace", []),
    })


async def _build_agent_graph(session, message: str, event_queue=None):
    """构建工作流图和初始状态（_execute_chat 和 _stream_chat 共用）"""
    messages = session.messages or []
    messages.append({"role": "user", "content": message})

    workflow = await Workflow.get_or_none(id=session.app.workflow_id)
    if not workflow:
        return None, None, None

    from core.workflow_engine import workflow_engine, AgentState
    from core.agent_factory import agent_factory
    from models.agent import Agent
    from models.mcp_server import AgentMcpLink
    from models.skill import AgentSkillLink

    worker_ids = workflow.worker_agent_ids or []
    agent_nodes = {}
    agent_names = []
    for wid in worker_ids:
        agent = await Agent.get_or_none(id=wid)
        if agent:
            mcp_links = await AgentMcpLink.filter(agent_id=agent.id).prefetch_related("mcp_server")
            skill_links = await AgentSkillLink.filter(agent_id=agent.id).prefetch_related("skill")
            config = {
                "name": agent.name, "agent_type": agent.agent_type, "role": agent.role,
                "llm_config": agent.llm_config, "llm_config_id": agent.llm_config_id,
                "http_config": agent.http_config, "claudecode_config": agent.claudecode_config,
                "system_prompt": agent.system_prompt,
                "knowledge_base_ids": agent.knowledge_base_ids or [],
                "mcp_servers": [{
                    "id": ml.mcp_server.id, "name": ml.mcp_server.name,
                    "base_url": ml.mcp_server.base_url, "headers": ml.mcp_server.headers,
                    "single_endpoint": ml.mcp_server.single_endpoint,
                    "enabled_tools": ml.enabled_tools, "enabled": ml.enabled,
                } for ml in mcp_links],
                "skills": [{"name": sl.skill.name, "skill_type": sl.skill.skill_type, "content": sl.skill.content} for sl in skill_links],
            }
            node_fn = await agent_factory.create(config, event_queue=event_queue)
            agent_nodes[agent.name] = node_fn
            agent_names.append(agent.name)

    wf_config = {"flow_type": workflow.flow_type, "worker_agent_ids": agent_names}

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
                "skills": [{"name": sl.skill.name, "skill_type": sl.skill.skill_type, "content": sl.skill.content} for sl in skill_links],
                "_available_workers": agent_names,
            }
            sup_node_fn = await agent_factory.create(sup_config, event_queue=event_queue)
            agent_nodes[sup_agent.name] = sup_node_fn

    graph = await workflow_engine.build_workflow(wf_config, agent_nodes)
    initial_state: AgentState = {
        "user_input": message, "messages": messages,
        "current_agent": "", "next_agent": "",
        "intermediate_results": {}, "final_answer": "",
        "need_human": False, "human_input": "", "error": None, "trace": [],
    }
    return graph, initial_state, agent_names, workflow.flow_type


async def _execute_chat(session: Session, message: str) -> dict:
    import time
    start = time.time()
    try:
        graph, initial_state, agent_names, flow_type = await _build_agent_graph(session, message)
        if graph is None:
            return {"final_answer": "工作流未配置", "intermediate_results": {}, "duration_ms": 0}

        logger.info(f"开始执行工作流: flow_type={flow_type}, workers={agent_names}")
        result = await graph.ainvoke(initial_state)
        logger.info(f"工作流执行完成")
        final_answer = result.get("final_answer", "")
        if not final_answer:
            intermediate = result.get("intermediate_results", {})
            if intermediate:
                last_key = list(intermediate.keys())[-1]
                final_answer = intermediate.get(last_key, "")

        msg_list = initial_state.get("messages") or []
        msg_list.append({"role": "assistant", "content": final_answer})
        session.messages = msg_list
        session.updated_at = datetime.now()
        await session.save()

        duration_ms = int((time.time() - start) * 1000)
        return {
            "final_answer": final_answer,
            "intermediate_results": result.get("intermediate_results", {}),
            "duration_ms": duration_ms,
            "trace": result.get("trace", []),
        }
    except Exception as e:
        logger.error(f"Chat execution failed: {e}")
        return {
            "final_answer": f"执行出错: {str(e)}",
            "intermediate_results": {},
            "duration_ms": 0,
        }


async def _stream_chat(session: Session, message: str):
    import time
    start = time.time()

    yield await sse_event("thinking", {"content": "正在分析问题..."})

    try:
        event_queue = asyncio.Queue()
        graph, initial_state, agent_names, flow_type = await _build_agent_graph(session, message, event_queue=event_queue)
        if graph is None:
            yield await sse_event("error", {"message": "工作流未配置"})
            return

        logger.info(f"开始执行工作流(stream): flow_type={flow_type}, workers={agent_names}")
        final_answer = ""
        seen_outputs = set()
        done = False

        async def run_graph():
            nonlocal final_answer, done
            async for chunk in graph.astream(initial_state, stream_mode="updates"):
                for node_name, update in chunk.items():
                    intermediate = update.get("intermediate_results") or {}
                    trace = update.get("trace") or []

                    for t in trace:
                        if t.get("type") == "supervisor_route":
                            target = t.get("target", "end")
                            if target != "end":
                                await event_queue.put({"type": "agent_call", "agent": target})

                    for agent_name, output in intermediate.items():
                        if agent_name.startswith("_"):
                            continue
                        output_str = str(output)
                        output_key = f"{agent_name}:{output_str[:50]}"
                        if output_key not in seen_outputs:
                            seen_outputs.add(output_key)
                            await event_queue.put({
                                "type": "agent_result",
                                "agent": agent_name,
                                "output": output_str[:500],
                            })

                    # Track final answer
                    for k, v in intermediate.items():
                        if not k.startswith("_"):
                            final_answer = str(v)
            done = True
            await event_queue.put({"type": "_done"})

        # Run graph and consume events concurrently
        graph_task = asyncio.create_task(run_graph())

        while not done or not event_queue.empty():
            try:
                evt = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                if evt.get("type") == "_done":
                    continue
                yield await sse_event(evt["type"], {k: v for k, v in evt.items() if k != "type"})
            except asyncio.TimeoutError:
                continue

        await graph_task

        # Send final answer as text event (frontend uses this for display)
        if final_answer:
            yield await sse_event("text", {"content": final_answer})

        # Update session
        messages = session.messages or []
        messages.append({"role": "assistant", "content": final_answer})
        session.messages = messages
        await session.save()

        yield await sse_event("done", {
            "session_id": session.id,
            "duration_ms": int((time.time() - start) * 1000),
        })
    except Exception as e:
        logger.error(f"Stream chat failed: {e}")
        yield await sse_event("error", {"message": str(e)})


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    """获取会话历史消息"""
    session = await Session.get_or_none(id=session_id)
    if not session:
        return error(code=404, message="会话不存在")
    return success(data={
        "session_id": session.id,
        "app_id": session.app_id,
        "messages": session.messages,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    })


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    """清除会话"""
    session = await Session.get_or_none(id=session_id)
    if not session:
        return error(code=404, message="会话不存在")
    await session.delete()
    return success(message="会话已清除")
