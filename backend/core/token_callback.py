"""LangChain 回调处理器 — 捕获每次 LLM 调用的 token 使用量

使用 contextvars 传递 task_id，支持并发安全。
"""

import contextvars
from langchain_core.callbacks import BaseCallbackHandler
from core.token_tracker import record_token_usage

# 当前正在执行的 task_id（由 workflow_executor 设置）
current_task_id: contextvars.ContextVar[str] = contextvars.ContextVar('current_task_id', default='')


class TokenCountCallback(BaseCallbackHandler):
    """捕获 LLM token 使用量的回调处理器"""

    def on_llm_end(self, response, **kwargs):
        """LLM 调用完成时提取 token 使用量"""
        task_id = current_task_id.get()
        if not task_id:
            return

        try:
            # 从 generations 中提取 usage_metadata
            generations = response.generations if response.generations else []
            for gen_list in generations:
                for gen in gen_list:
                    msg = getattr(gen, 'message', None)
                    if msg and hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                        um = msg.usage_metadata
                        model_name = None
                        if hasattr(msg, 'response_metadata') and msg.response_metadata:
                            model_name = msg.response_metadata.get('model_name')
                        record_token_usage(
                            task_id=task_id,
                            prompt_tokens=getattr(um, 'input_tokens', 0) or 0,
                            completion_tokens=getattr(um, 'output_tokens', 0) or 0,
                            total_tokens=getattr(um, 'total_tokens', 0) or 0,
                            model_name=model_name,
                        )
                        return

            # 回退: 从 llm_output 中提取
            llm_output = response.llm_output or {}
            usage = llm_output.get('usage', llm_output.get('token_usage', {}))
            if usage:
                record_token_usage(
                    task_id=task_id,
                    prompt_tokens=usage.get('prompt_tokens', 0) or usage.get('input_tokens', 0) or 0,
                    completion_tokens=usage.get('completion_tokens', 0) or usage.get('output_tokens', 0) or 0,
                    total_tokens=usage.get('total_tokens', 0) or 0,
                    model_name=llm_output.get('model_name'),
                )
        except Exception:
            pass
