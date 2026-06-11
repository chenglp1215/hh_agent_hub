import uuid
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
    })


async def _execute_chat(session: Session, message: str) -> dict:
    """执行工作流处理聊天消息（非流式内部方法）

    根据 session 关联的 app 找到对应工作流，构建代理节点并执行。

    Args:
        session: 当前会话对象，通过 session.app 关联到应用和工作流
        message: 用户输入的聊天消息

    Returns:
        包含 final_answer, intermediate_results, duration_ms 的字典
    """
    import time
    start = time.time()

    try:
        messages = session.messages or []
        messages.append({"role": "user", "content": message})

        workflow = await Workflow.get_or_none(id=session.app.workflow_id)
        if not workflow:
            return {"final_answer": "工作流未配置", "intermediate_results": {}, "duration_ms": 0}

        from core.workflow_engine import workflow_engine, AgentState
        from core.agent_factory import agent_factory
        from models.agent import Agent

        # 构建 Agent 节点
        worker_ids = workflow.worker_agent_ids or []
        agent_nodes = {}
        agent_names = []
        for wid in worker_ids:
            agent = await Agent.get_or_none(id=wid)
            if agent:
                config = {
                    "name": agent.name,
                    "agent_type": agent.agent_type,
                    "role": agent.role,
                    "llm_config": agent.llm_config,
                    "http_config": agent.http_config,
                    "claudecode_config": agent.claudecode_config,
                    "system_prompt": agent.system_prompt,
                    "knowledge_base_ids": agent.knowledge_base_ids or [],
                    "mcp_servers": [],
                    "skills": [],
                }
                node_fn = await agent_factory.create(config)
                agent_nodes[agent.name] = node_fn
                agent_names.append(agent.name)

        # 构建工作流配置
        wf_config = {
            "flow_type": workflow.flow_type,
            "worker_agent_ids": agent_names,
        }

        if workflow.flow_type == "supervisor" and workflow.supervisor_agent_id:
            sup_agent = await Agent.get_or_none(id=workflow.supervisor_agent_id)
            if sup_agent:
                wf_config["supervisor_agent_name"] = sup_agent.name
                sup_config = {
                    "name": sup_agent.name,
                    "agent_type": sup_agent.agent_type,
                    "role": sup_agent.role,
                    "llm_config": sup_agent.llm_config,
                    "system_prompt": sup_agent.system_prompt,
                    "knowledge_base_ids": sup_agent.knowledge_base_ids or [],
                    "mcp_servers": [],
                    "skills": [],
                }
                sup_node_fn = await agent_factory.create(sup_config)
                agent_nodes[sup_agent.name] = sup_node_fn

        graph = await workflow_engine.build_workflow(wf_config, agent_nodes)

        initial_state: AgentState = {
            "user_input": message,
            "messages": messages,
            "current_agent": "",
            "next_agent": "",
            "intermediate_results": {},
            "final_answer": "",
            "need_human": False,
            "human_input": "",
            "error": None,
        }

        result = await graph.ainvoke(initial_state)
        final_answer = result.get("final_answer", "")
        if not final_answer:
            intermediate = result.get("intermediate_results", {})
            if intermediate:
                last_key = list(intermediate.keys())[-1]
                final_answer = intermediate.get(last_key, "")

        messages.append({"role": "assistant", "content": final_answer})
        session.messages = messages
        session.updated_at = datetime.now()
        await session.save()

        duration_ms = int((time.time() - start) * 1000)
        return {
            "final_answer": final_answer,
            "intermediate_results": result.get("intermediate_results", {}),
            "duration_ms": duration_ms,
        }
    except Exception as e:
        logger.error(f"Chat execution failed: {e}")
        return {
            "final_answer": f"执行出错: {str(e)}",
            "intermediate_results": {},
            "duration_ms": 0,
        }


async def _stream_chat(session: Session, message: str):
    """SSE 流式聊天执行

    先发送 thinking 事件，然后执行工作流，逐步推送中间结果和最终答案。

    Args:
        session: 当前会话对象
        message: 用户输入的聊天消息

    Yields:
        SSE 格式化的事件字符串
    """
    yield await sse_event("thinking", {"content": "正在分析问题..."})

    try:
        result = await _execute_chat(session, message)

        intermediate = result.get("intermediate_results", {})
        for agent_name, output in intermediate.items():
            yield await sse_event("agent_call", {"agent": agent_name, "input": message})
            yield await sse_event("agent_result", {"agent": agent_name, "output": str(output)})

        final = result.get("final_answer", "")
        words = final.split()
        buffer = ""
        for word in words:
            buffer += word + " "
            yield await sse_event("text", {"content": buffer})

        yield await sse_event("done", {
            "session_id": session.id,
            "duration_ms": result.get("duration_ms", 0),
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
