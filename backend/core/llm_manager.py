from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatOllama
from loguru import logger
from core.token_callback import TokenCountCallback


class LLMManager:
    """LLM 实例工厂 — 根据配置创建 OpenAI / Anthropic / Ollama 实例"""

    PROVIDER_OPENAI = "openai"
    PROVIDER_ANTHROPIC = "anthropic"
    PROVIDER_OLLAMA = "ollama"

    def create(self, llm_config: Optional[Dict[str, Any]]) -> Any:
        if not llm_config:
            raise ValueError("llm_config is required")

        provider = llm_config.get("provider", self.PROVIDER_OPENAI)
        model = llm_config.get("model", "gpt-4o-mini")
        temperature = llm_config.get("temperature", 0.3)
        max_tokens = llm_config.get("max_tokens", 4096)
        api_key = llm_config.get("api_key")
        base_url = llm_config.get("base_url")

        if provider == self.PROVIDER_OPENAI:
            return self._create_openai(model, temperature, max_tokens, api_key, base_url)
        elif provider == self.PROVIDER_ANTHROPIC:
            return self._create_anthropic(model, temperature, max_tokens, api_key, base_url)
        elif provider == self.PROVIDER_OLLAMA:
            return self._create_ollama(model, temperature, max_tokens, base_url)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    def _create_openai(self, model: str, temperature: float, max_tokens: int,
                       api_key: Optional[str], base_url: Optional[str]) -> ChatOpenAI:
        kwargs = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "request_timeout": 120,
        }
        if api_key:
            kwargs["openai_api_key"] = api_key
        if base_url:
            kwargs["openai_api_base"] = base_url

        logger.info(f"Creating OpenAI LLM: model={model}, temperature={temperature}")
        return ChatOpenAI(**kwargs, callbacks=[TokenCountCallback()])

    def _create_anthropic(self, model: str, temperature: float, max_tokens: int,
                          api_key: Optional[str], base_url: Optional[str]) -> ChatAnthropic:
        kwargs = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if api_key:
            kwargs["anthropic_api_key"] = api_key
        if base_url:
            kwargs["anthropic_api_url"] = base_url

        logger.info(f"Creating Anthropic LLM: model={model}, temperature={temperature}")
        return ChatAnthropic(**kwargs, callbacks=[TokenCountCallback()])

    def _create_ollama(self, model: str, temperature: float, max_tokens: int,
                       base_url: Optional[str]) -> ChatOllama:
        kwargs = {
            "model": model,
            "temperature": temperature,
            "num_predict": max_tokens,
        }
        if base_url:
            kwargs["base_url"] = base_url
        else:
            kwargs["base_url"] = "http://localhost:11434"

        logger.info(f"Creating Ollama LLM: model={model}, temperature={temperature}")
        return ChatOllama(**kwargs)


llm_manager = LLMManager()
