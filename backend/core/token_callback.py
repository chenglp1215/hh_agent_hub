"""LangChain 回调处理器 — 捕获每次 LLM 调用的 token 使用量

使用 contextvars 传递 task_id，支持并发安全。
"""

import contextvars
from langchain_core.callbacks import BaseCallbackHandler
from core.token_tracker import record_token_usage

# 当前正在执行的 task_id（由 workflow_executor 设置）
current_task_id: contextvars.ContextVar[str] = contextvars.ContextVar('current_task_id', default='')

# tiktoken 编码器缓存
_tiktoken_encoder = None


def _get_tiktoken_encoder():
    """获取 tiktoken 编码器（cl100k_base，适用于 GPT-4/GPT-3.5 系列）"""
    global _tiktoken_encoder
    if _tiktoken_encoder is None:
        try:
            import tiktoken
            _tiktoken_encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _tiktoken_encoder = False  # 标记不可用
    return _tiktoken_encoder if _tiktoken_encoder is not None and _tiktoken_encoder is not False else None


def _estimate_tokens(text: str) -> int:
    """估算文本的 token 数量"""
    encoder = _get_tiktoken_encoder()
    if encoder:
        try:
            return len(encoder.encode(text))
        except Exception:
            pass
    # 粗略估算：1 中文字符 ≈ 2 token，1 英文单词 ≈ 1.3 token
    return max(1, len(text) // 2)


class TokenCountCallback(BaseCallbackHandler):
    """捕获 LLM token 使用量的回调处理器"""

    def __init__(self):
        super().__init__()
        self._prompt_texts: list = []

    def on_llm_start(self, serialized, prompts, **kwargs):
        """捕获输入 prompt 文本用于 token 估算"""
        self._prompt_texts = prompts or []
        from loguru import logger
        logger.debug(f"[TokenCallback] on_llm_start called, prompts={len(self._prompt_texts)}")

    def on_llm_end(self, response, **kwargs):
        """LLM 调用完成时提取 token 使用量"""
        task_id = current_task_id.get()
        if not task_id:
            return

        from loguru import logger
        try:
            # Debug: 确认回调被调用
            logger.debug(f"[TokenCallback] on_llm_end called, task_id={task_id}")

            model_name = None
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            found_usage = False

            # 从 generations 中提取
            generations = response.generations if response.generations else []
            logger.debug(f"[TokenCallback] generations count={len(generations)}")

            # Debug: 打印 response.llm_output
            llm_output_raw = response.llm_output
            logger.debug(f"[TokenCallback] llm_output={llm_output_raw}")
            for gen_list in generations:
                for gen in gen_list:
                    msg = getattr(gen, 'message', None)
                    if not msg:
                        continue

                    # 获取 model_name
                    rm = getattr(msg, 'response_metadata', None)
                    if rm:
                        model_name = model_name or rm.get('model_name') or rm.get('model')

                    # 方法1: usage_metadata（LangChain 标准格式）
                    um = getattr(msg, 'usage_metadata', None)
                    if um and (getattr(um, 'input_tokens', 0) or getattr(um, 'total_tokens', 0)):
                        prompt_tokens = getattr(um, 'input_tokens', 0) or 0
                        completion_tokens = getattr(um, 'output_tokens', 0) or 0
                        total_tokens = getattr(um, 'total_tokens', 0) or 0
                        found_usage = True
                        break

                    # 方法2: response_metadata.usage（OpenAI 兼容格式）
                    if rm:
                        usage = rm.get('usage', {})
                        if usage and (usage.get('prompt_tokens', 0) or usage.get('total_tokens', 0)):
                            prompt_tokens = usage.get('prompt_tokens', 0) or 0
                            completion_tokens = usage.get('completion_tokens', 0) or 0
                            total_tokens = usage.get('total_tokens', 0) or 0
                            found_usage = True
                            break

                if found_usage:
                    break

            # 方法3: llm_output
            if not found_usage:
                llm_output = response.llm_output or {}
                usage = llm_output.get('usage', llm_output.get('token_usage', {}))
                if usage and (usage.get('prompt_tokens', 0) or usage.get('total_tokens', 0)):
                    prompt_tokens = usage.get('prompt_tokens', 0) or usage.get('input_tokens', 0) or 0
                    completion_tokens = usage.get('completion_tokens', 0) or usage.get('output_tokens', 0) or 0
                    total_tokens = usage.get('total_tokens', 0) or 0
                    found_usage = True
                    model_name = model_name or llm_output.get('model_name')

            # 方法4: tiktoken 估算（兜底）
            if not found_usage:
                # 估算 prompt tokens
                for text in self._prompt_texts:
                    if text:
                        prompt_tokens += _estimate_tokens(text)
                # 估算 completion tokens
                for gen_list in generations:
                    for gen in gen_list:
                        msg = getattr(gen, 'message', None)
                        if msg and hasattr(msg, 'content') and msg.content:
                            completion_tokens += _estimate_tokens(msg.content)

            if prompt_tokens or completion_tokens or total_tokens:
                if not total_tokens:
                    total_tokens = prompt_tokens + completion_tokens
                record_token_usage(
                    task_id=task_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    model_name=model_name,
                )
        except Exception as e:
            from loguru import logger
            logger.debug(f"Token extraction error: {e}")
