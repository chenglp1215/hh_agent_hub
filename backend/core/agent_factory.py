from typing import Dict, Any, List
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import BaseTool
from langchain_core.messages import SystemMessage
from loguru import logger

from core.llm_manager import llm_manager
from core.mcp_client import mcp_client
from core.knowledge_injector import knowledge_injector


class _MCPTool(BaseTool):
    """将 MCP 工具封装为 LangChain BaseTool，用于 LangGraph ReAct Agent 的工具调用"""

    server_id: int
    mcp_tool_name: str

    async def _arun(self, **kwargs) -> str:
        return await mcp_client.call_tool(self.server_id, self.mcp_tool_name, kwargs)

    def _run(self, **kwargs) -> str:
        raise NotImplementedError("MCP 工具仅支持异步调用")


class AgentNodeFactory:
    """根据 Agent 配置创建 LangGraph Agent 节点

    支持三种 Agent 类型：
    - local: 基于 LangChain LLM + LangGraph ReAct Agent
    - http: 委托给远程 HTTP Agent
    - claudecode: 委托给 Claude Code CLI
    """

    def __init__(self):
        self.llm_manager = llm_manager

    async def create_local_agent(self, agent_config: Dict[str, Any]):
        """创建 local 类型 Agent 的执行节点

        local Agent 使用 LangGraph 的 create_react_agent 构建，
        集成 LLM、MCP Tools、Skills 和知识库注入。

        Args:
            agent_config: Agent 配置字典，包含 llm_config, mcp_servers, skills,
                         system_prompt, knowledge_base_ids 等字段

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

        # 3. 加载 Skill 内容作为 Prompt 上下文
        skill_context = self._load_skills_context(agent_config.get("skills", []))

        # 4. 构建完整 System Prompt
        base_prompt = agent_config.get("system_prompt", "")
        full_prompt = base_prompt + "\n\n" + skill_context if skill_context else base_prompt

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

            # 知识库注入（运行时根据用户输入动态检索并增强 Prompt）
            kb_ids = agent_config.get("knowledge_base_ids", [])
            if kb_ids and user_input:
                injected_prompt = await knowledge_injector.inject(
                    kb_ids, user_input, base_prompt
                )
                if skill_context:
                    injected_prompt += "\n\n" + skill_context
                if routing_instruction:
                    injected_prompt += routing_instruction
                # 使用注入后的 prompt 重建 agent
                injected_agent = create_react_agent(
                    model=llm, tools=tools,
                    state_modifier=SystemMessage(content=injected_prompt),
                )
                result = await injected_agent.ainvoke({
                    "messages": state.get("messages", []),
                })
            else:
                result = await react_agent.ainvoke({
                    "messages": state.get("messages", []),
                })

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
                    tools.append(_MCPTool(
                        name=t_name,
                        description=t.get("description", ""),
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

    def _load_skills_context(self, skills: List[Dict[str, Any]]) -> str:
        """将 Skills 转换为 Prompt 上下文文本

        支持两种 Skill 类型：
        - prompt: 直接嵌入 prompt_template 内容
        - file: 引用文件路径

        Args:
            skills: Skill 配置列表

        Returns:
            拼接后的上下文文本，空列表时返回空字符串
        """
        if not skills:
            return ""
        parts = []
        for skill in skills:
            name = skill.get("name", "")
            skill_type = skill.get("skill_type", "prompt")
            content = skill.get("content", {})

            if skill_type == "prompt" and isinstance(content, dict):
                template = content.get("prompt_template", "")
                if template:
                    parts.append(f"## Skill: {name}\n{template}")
            elif skill_type == "file" and isinstance(content, dict):
                file_path = content.get("file_path", "")
                if file_path:
                    parts.append(f"[引用文件: {file_path}]")

        return "\n\n".join(parts)

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

    async def create_claudecode_agent(self, agent_config: Dict[str, Any]):
        """创建 claudecode 类型 Agent 的执行节点

        将请求委托给 Claude Code CLI 运行器。

        Args:
            agent_config: Agent 配置字典，包含 claudecode_config 等字段

        Returns:
            异步函数，接收 state dict 并返回更新后的 state dict
        """
        from core.claude_code_runner import ClaudeCodeRunner
        runner = ClaudeCodeRunner(agent_config.get("claudecode_config", {}))
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

    async def create(self, agent_config: Dict[str, Any]):
        """根据 agent_type 创建对应的 Agent 节点

        Args:
            agent_config: Agent 配置字典，必须包含 agent_type 字段

        Returns:
            异步节点函数

        Raises:
            ValueError: 不支持的 agent_type
        """
        agent_type = agent_config.get("agent_type", "local")

        if agent_type == "local":
            return await self.create_local_agent(agent_config)
        elif agent_type == "http":
            return await self.create_http_agent(agent_config)
        elif agent_type == "claudecode":
            return await self.create_claudecode_agent(agent_config)
        else:
            raise ValueError(f"Unsupported agent type: {agent_type}")


agent_factory = AgentNodeFactory()
