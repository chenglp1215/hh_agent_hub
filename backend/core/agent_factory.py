import json
import asyncio
from typing import Dict, Any, List, Optional
from pydantic import create_model, Field
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import BaseTool
from langchain_core.messages import SystemMessage
from loguru import logger

from core.llm_manager import llm_manager
from core.mcp_client import mcp_client
from core.knowledge_injector import knowledge_injector


def _build_args_schema(input_schema: dict, tool_name: str):
    """将 MCP JSON Schema 转为 Pydantic 动态模型，用作 BaseTool.args_schema"""
    properties = input_schema.get("properties", {})
    if not properties:
        return None
    required_fields = input_schema.get("required", [])
    fields = {}
    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type", "string")
        desc = prop_schema.get("description", "")
        is_required = prop_name in required_fields
        default = ... if is_required else None
        annotation = {
            "string": str, "integer": int, "number": float,
            "boolean": bool, "array": list, "object": dict,
        }.get(prop_type, str)
        if not is_required:
            annotation = Optional[annotation]
        fields[prop_name] = (annotation, Field(default=default, description=desc))
    safe_name = "".join(c if c.isalnum() else "_" for c in tool_name)
    return create_model(f"{safe_name}_args", **fields)


class _MCPTool(BaseTool):
    """将 MCP 工具封装为 LangChain BaseTool，用于 LangGraph ReAct Agent 的工具调用"""

    server_id: int
    mcp_tool_name: str

    async def _arun(self, **kwargs) -> str:
        logger.info(f"[MCP Tool] {self.mcp_tool_name} called with {json.dumps(kwargs, ensure_ascii=False, default=str)}")
        try:
            result = await mcp_client.call_tool(self.server_id, self.mcp_tool_name, kwargs)
            logger.info(f"[MCP Tool] {self.mcp_tool_name} success, result length={len(result)}")
            return result
        except Exception as e:
            logger.error(f"[MCP Tool] {self.mcp_tool_name} failed: {e}")
            return f"工具调用失败 [{self.mcp_tool_name}]: {e}"

    def _run(self, **kwargs) -> str:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                future = concurrent.futures.Future()
                async def _call():
                    try:
                        result = await self._arun(**kwargs)
                        future.set_result(result)
                    except Exception as e:
                        future.set_exception(e)
                loop.create_task(_call())
                return future.result(timeout=120)
            else:
                return loop.run_until_complete(self._arun(**kwargs))
        except RuntimeError:
            return asyncio.run(self._arun(**kwargs))


class _SkillTool(BaseTool):
    """将 Skill 封装为 LangChain 按需加载工具"""

    skill_name: str
    skill_content: str

    async def _arun(self, **kwargs) -> str:
        logger.info(f"[Skill] 加载技能: {self.skill_name}")
        return self.skill_content

    def _run(self, **kwargs) -> str:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                future = concurrent.futures.Future()
                async def _call():
                    try:
                        result = await self._arun(**kwargs)
                        future.set_result(result)
                    except Exception as e:
                        future.set_exception(e)
                loop.create_task(_call())
                return future.result(timeout=120)
            else:
                return loop.run_until_complete(self._arun(**kwargs))
        except RuntimeError:
            return asyncio.run(self._arun(**kwargs))


class AgentNodeFactory:
    """根据 Agent 配置创建 LangGraph Agent 节点

    支持三种 Agent 类型：
    - local: 基于 LangChain LLM + LangGraph ReAct Agent
    - http: 委托给远程 HTTP Agent
    - claudecode: 委托给 Claude Code CLI
    """

    def __init__(self):
        self.llm_manager = llm_manager

    async def create_local_agent(self, agent_config: Dict[str, Any], event_queue: asyncio.Queue = None):
        """创建 local 类型 Agent 的执行节点

        Args:
            agent_config: Agent 配置字典
            event_queue: 可选，用于实时推送工具调用事件到 SSE 流

        Returns:
            异步函数，接收 state dict 并返回更新后的 state dict
        """
        agent_name = agent_config.get("name", "unknown")
        logger.info(f"Creating local agent: {agent_name}")

        # 1. 初始化 LLM（优先使用 llm_config_id 引用的系统配置）
        llm_config = await self._resolve_llm_config(agent_config)
        llm = self.llm_manager.create(llm_config)

        # 2. 加载 MCP 工具（连接 MCP Server 并转换为 LangChain BaseTool）
        tools = await self._load_mcp_tools(agent_config.get("mcp_servers", []))

        # 3. 加载 Skill 作为按需工具（而非全量注入 prompt）
        skill_tools, skill_summary = self._load_skill_tools(agent_config.get("skills", []))
        tools.extend(skill_tools)

        # 4. 构建完整 System Prompt（skill 摘要 + routing 指令）
        base_prompt = agent_config.get("system_prompt", "")
        full_prompt = base_prompt + "\n\n" + skill_summary if skill_summary else base_prompt

        # 4a. Supervisor 路由指令注入
        available_workers = agent_config.get("_available_workers", [])
        routing_instruction = ""
        if available_workers:
            worker_list = "\n".join(f"- {name}" for name in available_workers)
            routing_instruction = (
                f"\n\n---\n"
                f"你是工作流调度主管，负责将用户问题分派给合适的子代理。\n"
                f"可用的子代理：\n{worker_list}\n\n"
                f"请根据用户问题选择一个最合适的子代理来处理。\n"
                f"调度规则：\n"
                f"1. 首次收到用户问题时，选择一个最合适的子代理，输出 NEXT_AGENT: <名称>\n"
                f"2. 当子代理返回结果后，检查结果是否已完整回答用户问题。"
                f"如果已满足用户需求，必须输出 NEXT_AGENT: end\n"
                f"3. 不要重复调用同一个子代理处理相同的问题\n\n"
                f"在回复的最后，单独用一行标明路由决策，格式如下：\n"
                f"NEXT_AGENT: <代理名称>\n"
                f"或\n"
                f"NEXT_AGENT: end"
            )
            full_prompt += routing_instruction

        # 5. 创建 ReAct Agent
        react_agent = create_react_agent(
            model=llm,
            tools=tools,
            state_modifier=SystemMessage(content=full_prompt),
        )

        # 6. 返回节点函数
        async def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
            import time as time_mod
            t0 = time_mod.time()
            user_input = state.get("user_input", "")
            logger.info(f"[Agent: {agent_name}] 开始执行，输入长度={len(user_input)}")

            trace = state.get("trace") or []
            trace.append({"type": "agent_start", "agent": agent_name, "input_len": len(user_input)})

            kb_ids = agent_config.get("knowledge_base_ids", [])
            agent = react_agent
            if kb_ids and user_input:
                injected_prompt = await knowledge_injector.inject(kb_ids, user_input, base_prompt)
                if skill_summary:
                    injected_prompt += "\n\n" + skill_summary
                if routing_instruction:
                    injected_prompt += routing_instruction
                agent = create_react_agent(model=llm, tools=tools, state_modifier=SystemMessage(content=injected_prompt))

            input_msgs = state.get("messages", [])

            # Stream mode: push tool events in real-time via event_queue
            if event_queue is not None:
                all_messages = []
                async for event in agent.astream_events(
                    {"messages": input_msgs}, version="v2"
                ):
                    kind = event.get("event", "")
                    data = event.get("data", {})
                    if kind == "on_tool_start":
                        await event_queue.put({
                            "type": "tool_call",
                            "agent": agent_name,
                            "tool": event.get("name", ""),
                            "args": str(data.get("input", {}))[:200],
                        })
                    elif kind == "on_tool_end":
                        await event_queue.put({
                            "type": "tool_result",
                            "agent": agent_name,
                            "tool": event.get("name", ""),
                            "result": str(data.get("output", ""))[:300],
                        })
                    elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                        all_messages = data.get("output", {}).get("messages", [])
                result = {"messages": all_messages}
            else:
                result = await agent.ainvoke({"messages": input_msgs})

            # 提取最后一条消息的内容作为输出
            last_message = (
                result.get("messages", [])[-1] if result.get("messages") else None
            )
            output = last_message.content if last_message else ""

            # 聚合中间结果
            intermediate = state.get("intermediate_results", {})
            intermediate[agent_name] = output

            elapsed = int((time_mod.time() - t0) * 1000)
            logger.info(f"[Agent: {agent_name}] 执行完成，输出长度={len(output)}，耗时={elapsed}ms")
            trace.append({
                "type": "agent_end", "agent": agent_name,
                "output_len": len(output), "elapsed_ms": elapsed,
            })
            return {
                "messages": result.get("messages", []),
                "intermediate_results": intermediate,
                "trace": trace,
            }

        return agent_node

    async def _load_mcp_tools(self, mcp_servers: List[Dict[str, Any]]) -> List[BaseTool]:
        """连接 MCP Server 并发现可用工具，转换为 LangChain BaseTool 列表

        Args:
            mcp_servers: MCP Server 配置列表，每项包含 id, base_url, headers,
                        enabled_tools 等字段

        Returns:
            BaseTool 列表，供 LangGraph ReAct Agent 使用
        """
        tools: List[BaseTool] = []
        for server_cfg in mcp_servers:
            if not server_cfg.get("enabled", True):
                continue
            try:
                server_id = server_cfg.get("id")
                base_url = server_cfg.get("base_url")
                headers = server_cfg.get("headers", {})
                enabled_tools = server_cfg.get("enabled_tools", [])

                if not base_url:
                    logger.warning(
                        f"MCP server {server_cfg.get('name')} has no base_url, skipping"
                    )
                    continue

                # 连接 MCP Server
                single_endpoint = server_cfg.get("single_endpoint", False)
                await mcp_client.connect(server_id, base_url, headers, single_endpoint=single_endpoint)

                # 发现工具列表
                raw_tools = await mcp_client.discover_tools(server_id)

                # 转换为 LangChain BaseTool
                for t in raw_tools:
                    t_name = t["name"]
                    if enabled_tools and t_name not in enabled_tools:
                        continue
                    input_schema = t.get("inputSchema", {})
                    args_schema = _build_args_schema(input_schema, t_name)
                    tools.append(_MCPTool(
                        name=t_name,
                        description=t.get("description", ""),
                        args_schema=args_schema,
                        server_id=server_id,
                        mcp_tool_name=t_name,
                    ))

                logger.info(
                    f"Loaded {len(raw_tools)} tools from MCP server "
                    f"'{server_cfg.get('name')}'"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to load MCP tools from "
                    f"'{server_cfg.get('name')}': {e}"
                )
        return tools

    async def _resolve_llm_config(self, agent_config: Dict[str, Any]) -> Dict[str, Any]:
        """解析 LLM 配置：优先使用 llm_config_id 引用的系统配置"""
        llm_config = agent_config.get("llm_config")
        llm_config_id = agent_config.get("llm_config_id")

        if llm_config_id:
            from models.llm_config import LlmConfig
            sys_cfg = await LlmConfig.get_or_none(id=llm_config_id)
            if sys_cfg:
                # 系统配置为基底，agent 内联配置可覆盖 api_key/base_url
                inline = llm_config or {}
                return {
                    "provider": sys_cfg.provider,
                    "model": sys_cfg.model,
                    "temperature": sys_cfg.temperature,
                    "max_tokens": sys_cfg.max_tokens,
                    "api_key": inline.get("api_key") or sys_cfg.api_key,
                    "base_url": inline.get("base_url") or sys_cfg.base_url,
                }
            else:
                logger.warning(
                    f"LLM config id={llm_config_id} not found for agent "
                    f"'{agent_config.get('name')}', falling back to inline config"
                )

        if not llm_config:
            raise ValueError(
                f"Agent '{agent_config.get('name', 'unknown')}' has no LLM config. "
                "Please assign an LLM configuration in agent settings."
            )
        return llm_config

    def _load_skill_tools(self, skills: List[Dict[str, Any]]) -> tuple:
        """将 Skills 封装为 LangChain BaseTool 列表 + 摘要文本

        每种 Skill 生成一个工具，Agent 按需调用加载，避免全量注入 prompt。
        同时返回 skill 摘要，简要列出可用 skill 名称和用途。

        Returns:
            (tools_list, summary_text)
        """
        if not skills:
            return [], ""

        tools = []
        summaries = []
        for skill in skills:
            name = skill.get("name", "")
            skill_type = skill.get("skill_type", "prompt")
            content = skill.get("content", {})

            if skill_type == "prompt" and isinstance(content, dict):
                template = content.get("prompt_template", "")
                desc = content.get("description", name)
                summaries.append(f"- {name}: {desc[:80]}")
                if template:
                    tools.append(_SkillTool(
                        name=f"skill_{name}",
                        description=f"加载技能「{name}」的详细指导。{desc[:100]}。当需要{name}相关的专业知识时调用此工具。",
                        skill_name=name,
                        skill_content=template,
                    ))
            elif skill_type == "file" and isinstance(content, dict):
                file_path = content.get("file_path", "")
                summaries.append(f"- {name}: 引用文件 {file_path}")
                if file_path:
                    tools.append(_SkillTool(
                        name=f"skill_{name}",
                        description=f"加载技能「{name}」中的文件内容。引用文件: {file_path}",
                        skill_name=name,
                        skill_content=f"[引用文件: {file_path}]",
                    ))

        summary = ""
        if summaries:
            summary = "可用技能（按需调用对应 skill_ 工具加载详情）:\n" + "\n".join(summaries)

        return tools, summary


    async def create_http_agent(self, agent_config: Dict[str, Any]):
        """创建 http 类型 Agent 的执行节点

        将请求委托给远程 HTTP Agent 服务。

        Args:
            agent_config: Agent 配置字典，包含 http_config 等字段

        Returns:
            异步函数，接收 state dict 并返回更新后的 state dict
        """
        from core.http_agent_client import HttpAgentClient
        client = HttpAgentClient(agent_config.get("http_config", {}))
        agent_name = agent_config.get("name", "unknown")

        async def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
            user_input = state.get("user_input", "")
            session_id = state.get("session_id", "")
            try:
                output = await client.send(user_input, session_id, state)
            except Exception as e:
                output = f"HTTP Agent error: {str(e)}"
                logger.error(f"HTTP Agent {agent_name} failed: {e}")

            intermediate = state.get("intermediate_results", {})
            intermediate[agent_name] = output
            return {
                "intermediate_results": intermediate,
            }

        return agent_node

    async def create_claudecode_agent(self, agent_config: Dict[str, Any],
                                       mcp_servers: List[Dict] = None,
                                       kb_content: List[Dict] = None,
                                       skill_content: List[Dict] = None):
        """创建 claudecode 类型 Agent 的执行节点

        将请求委托给 Claude Code CLI 运行器，并传递已解析的资源上下文。

        Args:
            agent_config: Agent 配置字典，包含 claudecode_config 等字段
            mcp_servers: 关联的 MCP Server 配置列表（含 base_url, headers 等）
            kb_content: 关联知识库的 ContentBlock 列表（含 heading_path, body 等）
            skill_content: 关联 Skill 的内容列表（含 name, content 等）

        Returns:
            异步函数，接收 state dict 并返回更新后的 state dict
        """
        from core.claude_code_runner import ClaudeCodeRunner
        runner = ClaudeCodeRunner(
            config=agent_config.get("claudecode_config", {}),
            mcp_servers=mcp_servers,
            kb_content=kb_content,
            skill_content=skill_content,
        )
        agent_name = agent_config.get("name", "unknown")

        async def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
            user_input = state.get("user_input", "")
            session_id = state.get("session_id", "")
            try:
                output = await runner.invoke(user_input, session_id, state)
            except Exception as e:
                output = f"Claude Code Agent error: {str(e)}"
                logger.error(f"Claude Code Agent {agent_name} failed: {e}")

            intermediate = state.get("intermediate_results", {})
            intermediate[agent_name] = output
            return {
                "intermediate_results": intermediate,
            }

        return agent_node

    async def create(self, agent_config: Dict[str, Any], event_queue=None):
        agent_type = agent_config.get("agent_type", "local")

        if agent_type == "local":
            return await self.create_local_agent(agent_config, event_queue=event_queue)
        elif agent_type == "http":
            return await self.create_http_agent(agent_config)
        elif agent_type == "claudecode":
            return await self.create_claudecode_agent(agent_config)
        else:
            raise ValueError(f"Unsupported agent type: {agent_type}")


agent_factory = AgentNodeFactory()
