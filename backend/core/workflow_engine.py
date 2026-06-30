import re
import time as time_mod
from typing import TypedDict, List, Any, Dict, Optional
from typing_extensions import NotRequired
from langgraph.graph import StateGraph, END
from loguru import logger

from core.agent_call_log import agent_call_logger


class AgentState(TypedDict):
    user_input: str
    messages: List[Any]
    current_agent: str
    next_agent: str
    intermediate_results: Dict[str, Any]
    final_answer: str
    need_human: bool
    human_input: str
    trace: List[Dict[str, Any]]
    error: Optional[str]
    session_id: str
    session_workspace: str
    termination_reason: Optional[str]
    partial_completion: bool
    # Agent 追踪字段（执行追踪用）
    _trace_id: NotRequired[str]
    _parent_span_id: NotRequired[str]
    task_id: NotRequired[str]
    # 原始用户需求（跨轮次保留，供 supervisor 感知完整计划）
    _original_user_input: NotRequired[str]


class WorkflowEngine:
    """LangGraph 工作流编排引擎"""

    def __init__(self):
        pass

    async def build_workflow(self, workflow_config: Dict[str, Any],
                             agent_nodes: Dict[str, Any],
                             agent_configs: Dict[str, Dict[str, Any]] = None):
        """根据工作流配置和 Agent 节点构建 LangGraph

        Args:
            workflow_config: 工作流配置字典，包含 flow_type, supervisor_agent_id,
                            worker_agent_ids, edges, parallel_groups, human_interrupts
            agent_nodes: Agent 名称到节点函数的映射字典

        Returns:
            编译后的 LangGraph StateGraph（可调用 compiled.ainvoke 执行）

        Raises:
            ValueError: 不支持的 flow_type 或缺少必要节点
        """
        flow_type = workflow_config.get("flow_type", "sequential")

        if flow_type == "supervisor":
            return await self._build_supervisor(workflow_config, agent_nodes, agent_configs)
        elif flow_type == "sequential":
            return await self._build_sequential(workflow_config, agent_nodes)
        elif flow_type == "graph":
            return await self._build_graph(workflow_config, agent_nodes)
        else:
            raise ValueError(f"Unsupported flow type: {flow_type}")

    async def _build_supervisor(self, config: Dict[str, Any],
                                agent_nodes: Dict[str, Any],
                                agent_configs: Dict[str, Dict[str, Any]] = None):
        """监督者模式：Supervisor Agent 路由任务到 Worker Agents

        Supervisor Agent 收到用户输入后，决定将任务路由给哪个 Worker Agent，
        Worker Agent 执行完毕后将结果返回 Supervisor，由其决定下一步路由或结束。

        Args:
            config: 工作流配置，需包含 supervisor_agent_name 和 worker_agent_ids
            agent_nodes: Agent 名称到节点函数的映射

        Returns:
            编译后的 LangGraph StateGraph
        """
        supervisor_name = config.get("supervisor_agent_name", "supervisor")
        supervisor_node = agent_nodes.get(supervisor_name)

        if not supervisor_node:
            raise ValueError(f"Supervisor agent '{supervisor_name}' not found in agent_nodes")

        graph = StateGraph(AgentState)

        # Add supervisor node (wrapped to parse routing decision)
        config_rounds = config.get("max_supervisor_rounds", 5)
        max_supervisor_rounds = min(config_rounds, 20)

        async def supervisor_wrapper(state: AgentState) -> dict:
            t0 = time_mod.time()
            trace = state.get("trace") or []
            intermediate = state.get("intermediate_results") or {}
            rounds = intermediate.get("_supervisor_rounds", 0)

            # Agent call logging: trace context
            _trace_id = state.get("_trace_id", "")
            _parent_span_id = state.get("_parent_span_id", "")
            _span_id = agent_call_logger.start_span(_parent_span_id) if _trace_id else ""

            if rounds >= max_supervisor_rounds:
                logger.warning(
                    f"[Supervisor: {supervisor_name}] 已达最大轮次 {max_supervisor_rounds}，强制结束"
                )
                intermediate["_supervisor_rounds"] = rounds + 1
                trace.append({"type": "supervisor_force_end", "round": rounds + 1})

                # 汇总已有中间结果
                summary_parts = []
                for k, v in intermediate.items():
                    if k.startswith("_") or k == supervisor_name:
                        continue
                    summary_parts.append(f"[{k}]:\n{str(v)[:3000]}")
                if summary_parts:
                    final_answer = "轮次耗尽，以下为已有结果：\n\n" + "\n\n".join(summary_parts)
                else:
                    final_answer = "轮次耗尽，未产生中间结果。"

                return {
                    "next_agent": "end",
                    "final_answer": final_answer,
                    "intermediate_results": intermediate,
                    "trace": trace,
                    "termination_reason": "rounds_exhausted",
                    "partial_completion": True,
                }

            logger.info(f"[Supervisor: {supervisor_name}] 第 {rounds + 1} 轮调度决策")
            trace.append({"type": "supervisor_start", "round": rounds + 1})

            # 问候语快速短路：第一轮且用户输入是简单问候，直接返回，不调用 LLM
            if rounds == 0:
                GREETING_PATTERNS = (
                    r'^(你好|您好|嗨|hi|hello|hey|在吗|在不在|早上好|下午好|晚上好|'
                    r'good morning|good afternoon|good evening|'
                    r'嗯|哦|好的|谢谢|多谢|感谢|ok|okay)$'
                )
                user_input = state.get("user_input", "").strip()
                if re.match(GREETING_PATTERNS, user_input, re.IGNORECASE):
                    greeting_reply = f"你好！我是 {supervisor_name}，有什么可以帮你的吗？"
                    logger.info(f"[Supervisor: {supervisor_name}] 问候语检测，直接回复，不路由到子代理")
                    trace.append({"type": "supervisor_greeting_shortcut", "round": 1})
                    intermediate["_supervisor_rounds"] = 1
                    return {
                        "next_agent": "end",
                        "final_answer": greeting_reply,
                        "intermediate_results": intermediate,
                        "trace": trace,
                    }

            # 将前一轮 worker 的结果注入 messages，让 supervisor 感知到子代理已完成任务
            state_with_context = dict(state)
            msgs = list(state.get("messages", []))

            # 每轮注入轮次信息
            remaining = max_supervisor_rounds - rounds
            msgs.append({"role": "system", "content": f"当前第 {rounds + 1} 轮调度，剩余 {remaining} 轮，最多 {max_supervisor_rounds} 轮。"})

            worker_context_injected = False
            if rounds > 0:
                worker_outputs = []
                for k, v in intermediate.items():
                    if k.startswith("_"):
                        continue
                    if k == supervisor_name:
                        continue
                    worker_outputs.append(f"[{k} 的返回结果]:\n{str(v)[:3000]}")
                if worker_outputs:
                    context_msg = "\n\n".join(worker_outputs)
                    injected = f"以下子代理已完成任务。请对照【用户原始需求】，逐项检查是否所有需求点都已满足：\n\n{context_msg}\n\n未满足的继续调度，全部满足后再输出 NEXT_AGENT: end。"
                    msgs.append({"role": "user", "content": injected})
                    worker_context_injected = True
                    logger.info(f"[Supervisor: {supervisor_name}] 注入 Worker 结果：{context_msg[:200]}...")

            # 注入原始用户需求作为最后一条消息，利用近因效应确保 Supervisor 不遗忘完整计划
            # Worker 节点从 result["messages"] 获取消息，不会包含此注入
            orig = state.get("_original_user_input", "")
            if orig:
                msgs.append({"role": "user", "content": f"【用户原始需求】{orig}"})
                logger.info(f"[Supervisor: {supervisor_name}] 注入原始需求（长度={len(orig)}）")

            state_with_context["messages"] = msgs

            result = await supervisor_node(state_with_context)
            # 清理注入的上下文/轮次消息，防止持久化到 session.messages 污染后续对话
            out_msgs = result.get("messages", [])
            if out_msgs:
                _injected_contents = {f"当前第 {rounds + 1} 轮调度，剩余 {remaining} 轮，最多 {max_supervisor_rounds} 轮。"}
                if worker_context_injected:
                    _injected_contents.add(injected)
                def _is_not_injected(m):
                    content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
                    return content not in _injected_contents
                result["messages"] = [m for m in out_msgs if _is_not_injected(m)]
            trace = result.get("trace") or trace
            intermediate = result.get("intermediate_results") or {}
            intermediate["_supervisor_rounds"] = rounds + 1
            output = intermediate.get(supervisor_name, "")

            match = re.search(r'^NEXT_AGENT:\s*(.+)$', output, re.MULTILINE)
            if match:
                raw = match.group(1).strip()
                next_agent = "end" if raw.lower() == "end" else raw

                # 校验目标 Agent 是否存在
                if next_agent != "end" and next_agent not in agent_nodes:
                    logger.warning(f"[Supervisor: {supervisor_name}] 指向不存在的 Agent: {next_agent}，回退到 END")
                    trace.append({
                        "type": "routing_correction",
                        "round": rounds + 1,
                        "original_target": next_agent,
                        "actual_target": "end",
                        "reason": "target_not_found"
                    })
                    next_agent = "end"
                else:
                    trace.append({"type": "supervisor_route", "round": rounds + 1, "target": next_agent})

                result["next_agent"] = next_agent
                logger.info(f"[Supervisor: {supervisor_name}] 路由决策: {result['next_agent']}")
                cleaned = re.sub(
                    r'^NEXT_AGENT:\s*.+$\n?', '', output, flags=re.MULTILINE
                ).strip()
                if cleaned:
                    intermediate[supervisor_name] = cleaned

                # 路由到 end 时，cleaned 内容就是最终回复
                if next_agent == "end" and cleaned:
                    result["final_answer"] = cleaned

                # 将 supervisor 的任务描述作为 worker 的输入（主管安排的独立任务）
                # 子代理只看到主管整理的任务描述，看不到用户原始消息
                if next_agent != "end" and cleaned:
                    result["user_input"] = cleaned
                    result["messages"] = [{"role": "user", "content": cleaned}]
            else:
                result["next_agent"] = "end"
                trace.append({"type": "supervisor_end", "round": rounds + 1, "reason": "no NEXT_AGENT marker"})
                logger.warning(f"[Supervisor: {supervisor_name}] 未找到 NEXT_AGENT 标记，结束工作流")
            result["intermediate_results"] = intermediate
            result["trace"] = trace

            # --- Trace context propagation ---
            # agent_node 已记录完整日志（system_prompt/input/output/token），此处仅传播 trace 上下文
            if _trace_id:
                result["_trace_id"] = _trace_id
                result["_parent_span_id"] = _span_id

            # 保留原始用户需求，供 supervisor 跨轮次感知完整计划
            if "_original_user_input" not in result:
                result["_original_user_input"] = state.get("_original_user_input", "")
            return result

        graph.add_node("supervisor", supervisor_wrapper)

        # Add worker nodes and connect them back to supervisor
        worker_names = []
        for name in config.get("worker_agent_ids", []):
            if isinstance(name, int):
                continue  # Skip raw IDs (should be resolved to names by caller)
            if name in agent_nodes:
                graph.add_node(name, agent_nodes[name])
                graph.add_edge(name, "supervisor")
                worker_names.append(name)

        # Supervisor routing: use next_agent from state to decide where to route
        async def route_supervisor(state: AgentState) -> str:
            next_agent = state.get("next_agent", "end")
            if next_agent == "end" or next_agent == END:
                return END
            if next_agent in worker_names:
                return next_agent
            return END

        graph.add_conditional_edges("supervisor", route_supervisor)
        graph.set_entry_point("supervisor")

        compiled = graph.compile()
        logger.info(f"Supervisor workflow built: supervisor={supervisor_name}, workers={worker_names}")
        return compiled

    async def _build_sequential(self, config: Dict[str, Any],
                                agent_nodes: Dict[str, Any]):
        """顺序模式：Agent 按流水线顺序依次执行

        每个 Agent 的输出自动传递给下一个 Agent 作为输入上下文。

        Args:
            config: 工作流配置，需包含 worker_agent_ids（有序列表）
            agent_nodes: Agent 名称到节点函数的映射

        Returns:
            编译后的 LangGraph StateGraph
        """
        agent_names = config.get("worker_agent_ids", [])

        graph = StateGraph(AgentState)
        previous_name = None

        for i, name in enumerate(agent_names):
            if isinstance(name, int):
                continue
            node_fn = agent_nodes.get(name)
            if not node_fn:
                logger.warning(f"Agent '{name}' not found, skipping")
                continue

            node_id = f"agent_{i}_{name}"
            graph.add_node(node_id, node_fn)

            if previous_name:
                graph.add_edge(previous_name, node_id)
            previous_name = node_id

        if previous_name:
            graph.add_edge(previous_name, END)
            graph.set_entry_point(f"agent_0_{agent_names[0]}")
        else:
            raise ValueError("No valid agent nodes found for sequential workflow")

        compiled = graph.compile()
        logger.info(f"Sequential workflow built: {len(agent_names)} agents")
        return compiled

    async def _build_graph(self, config: Dict[str, Any],
                           agent_nodes: Dict[str, Any]):
        """图模式：自定义有向图，按 edges 定义连接

        支持三种边类型：
        - normal: 普通有向边，from -> to
        - conditional: 条件边，根据 condition_field 的值选择路由
        - start/end: 特殊节点标识入口和出口

        Args:
            config: 工作流配置，需包含 edges 列表，每项含 from, to, type 等字段
            agent_nodes: Agent 名称到节点函数的映射

        Returns:
            编译后的 LangGraph StateGraph
        """
        edges: List[Dict] = config.get("edges", [])

        graph = StateGraph(AgentState)

        # Collect unique node names from edges
        node_names: set = set()
        for edge in edges:
            node_names.add(edge.get("from", ""))
            node_names.add(edge.get("to", ""))

        # Add agent nodes
        for name in node_names:
            if name == "start" or name == "end" or not name:
                continue
            if name in agent_nodes:
                graph.add_node(name, agent_nodes[name])

        # Process edges
        conditional_routes: Dict[str, List[Dict]] = {}

        for edge in edges:
            from_node = edge.get("from", "")
            to_node = edge.get("to", "")
            edge_type = edge.get("type", "normal")

            if from_node == "start":
                if to_node != "end":
                    graph.set_entry_point(to_node)
            elif to_node == "end":
                if edge_type == "normal":
                    graph.add_edge(from_node, END)
            elif edge_type == "conditional":
                if from_node not in conditional_routes:
                    conditional_routes[from_node] = []
                conditional_routes[from_node].append(edge)
            else:
                graph.add_edge(from_node, to_node)

        # Add conditional edges
        for from_node, routes in conditional_routes.items():
            condition_field = routes[0].get("condition_field", "")

            async def make_router(field: str, route_list: List[Dict]):
                async def router(state: AgentState) -> str:
                    field_value = state.get(field, "")
                    for route in route_list:
                        if route.get("condition") == str(field_value) or route.get("condition") == "true":
                            target = route.get("to", "")
                            if target == "end":
                                return END
                            return target
                    return END

                return router

            route_fn = await make_router(condition_field, routes)
            graph.add_conditional_edges(from_node, route_fn)

        compiled = graph.compile()
        logger.info(f"Graph workflow built: {len(edges)} edges, {len(node_names)} nodes")
        return compiled


workflow_engine = WorkflowEngine()
