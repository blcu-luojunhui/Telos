"""
LLM 客户端工厂：基于配置创建 OpenAI 兼容异步客户端。

交互层已统一使用 src.domain.interaction.llm.get_chat_model (LangChain ChatOpenAI)。
本模块保留底层 AsyncOpenAI 客户端工厂，供非 LangChain 场景使用。
"""

from __future__ import annotations

from typing import Any, Optional

from src.config import Config, LLMProviderType


def get_llm_client_and_model(
    provider: Optional[LLMProviderType] = None,
) -> tuple[Any, str]:
    """
    根据配置返回 (AsyncOpenAI client, model_name)。
    DeepSeek / OpenAI 均使用 OpenAI 兼容接口。
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise RuntimeError("请安装 openai: pip install openai")

    cfg = Config()
    prov = provider or cfg.llm_provider

    if prov == "deepseek":
        d = cfg.deepseek
        if not d.api_key:
            raise ValueError("DeepSeek API Key 未配置（DEEP_SEEK_API_KEY）")
        client = AsyncOpenAI(api_key=d.api_key, base_url=d.base_url)
        return client, d.model

    if prov == "openai":
        o = cfg.openai
        if not o.api_key:
            raise ValueError("OpenAI API Key 未配置（OPENAI_API_KEY）")
        client = AsyncOpenAI(api_key=o.api_key)
        return client, o.model

    raise ValueError(f"不支持的 LLM 供应商: {prov}，可选: deepseek | openai")
