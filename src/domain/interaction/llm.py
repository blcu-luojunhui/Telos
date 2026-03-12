"""
LangChain ChatModel 工厂：根据项目配置创建 ChatOpenAI 实例。

支持 deepseek（通过 base_url 兼容 OpenAI 接口）和 openai 两种 provider。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from langchain_openai import ChatOpenAI

from src.config import Config, LLMProviderType


def get_chat_model(
    provider: Optional[LLMProviderType] = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
) -> ChatOpenAI:
    """
    根据配置返回 LangChain ChatOpenAI 实例（兼容 DeepSeek）。
    每次调用返回新实例，适用于不同温度 / token 限制场景。
    """
    cfg = Config()
    prov = provider or cfg.llm_provider

    if prov == "deepseek":
        d = cfg.deepseek
        if not d.api_key:
            raise ValueError("DeepSeek API Key 未配置（DEEP_SEEK_API_KEY）")
        return ChatOpenAI(
            model=model or d.model,
            api_key=d.api_key,
            base_url=d.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if prov == "openai":
        o = cfg.openai
        if not o.api_key:
            raise ValueError("OpenAI API Key 未配置（OPENAI_API_KEY）")
        return ChatOpenAI(
            model=model or o.model,
            api_key=o.api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    raise ValueError(f"不支持的 LLM 供应商: {prov}，可选: deepseek | openai")


@lru_cache(maxsize=4)
def get_default_chat_model() -> ChatOpenAI:
    """获取默认配置的 ChatModel（单例缓存）。"""
    return get_chat_model(temperature=0.1)
