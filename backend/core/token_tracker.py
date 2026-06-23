"""Token 消耗追踪器 — 按 task_id 聚合 LLM token 使用量"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model_name: Optional[str] = None


# 全局按 task_id 累积
_token_usage: Dict[str, TokenUsage] = {}


def record_token_usage(task_id: str, prompt_tokens: int = 0,
                       completion_tokens: int = 0, total_tokens: int = 0,
                       model_name: Optional[str] = None):
    """记录一次 LLM 调用的 token 使用量"""
    if not task_id:
        return
    usage = _token_usage.get(task_id)
    if not usage:
        usage = TokenUsage()
        _token_usage[task_id] = usage
    usage.prompt_tokens += prompt_tokens
    usage.completion_tokens += completion_tokens
    usage.total_tokens += total_tokens
    if model_name:
        usage.model_name = model_name


def get_token_usage(task_id: str) -> TokenUsage:
    """获取并清除指定 task 的 token 使用量"""
    return _token_usage.pop(task_id, TokenUsage())


def extract_usage_from_response(response) -> dict:
    """从 LangChain AIMessage 响应中提取 token 使用量

    支持 OpenAI、Anthropic 等 provider 的 usage_metadata 格式。
    """
    try:
        # LangChain >= 0.2 的 usage_metadata
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            um = response.usage_metadata
            return {
                "prompt_tokens": getattr(um, 'input_tokens', 0) or 0,
                "completion_tokens": getattr(um, 'output_tokens', 0) or 0,
                "total_tokens": getattr(um, 'total_tokens', 0) or 0,
            }
        # response_metadata 中的 usage
        if hasattr(response, 'response_metadata') and response.response_metadata:
            usage = response.response_metadata.get('usage', {})
            if usage:
                return {
                    "prompt_tokens": usage.get('prompt_tokens', 0) or 0,
                    "completion_tokens": usage.get('completion_tokens', 0) or 0,
                    "total_tokens": usage.get('total_tokens', 0) or 0,
                }
    except Exception:
        pass
    return {}
