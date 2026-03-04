"""
外部服务封装：LLM（OpenAI 兼容）等。
统一输入/输出类型、模型调用、Tool 调用，全部异步。
"""

from .llm import (
    ChatCompletionResult,
    ChatMessage,
    LLMGateway,
    ToolCall,
    ToolDef,
    get_llm_client_and_model,
)

__all__ = [
    "ChatCompletionResult",
    "ChatMessage",
    "LLMGateway",
    "ToolCall",
    "ToolDef",
    "get_llm_client_and_model",
]
