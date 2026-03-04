"""
LLM 客户端封装：基于配置创建 OpenAI 兼容客户端，提供异步 chat / tool 调用。
"""

from __future__ import annotations

from typing import Any, List, Optional, Union

from src.config import Config, LLMProviderType

from src.infra.shared.types import (
    ChatCompletionResult,
    ChatMessage,
    ToolCall,
    ToolDef,
)


def get_llm_client_and_model(
    provider: Optional[LLMProviderType] = None,
) -> tuple[Any, str]:
    """
    根据配置返回 (AsyncOpenAI client, model_name)。
    DeepSeek / OpenAI 均使用 OpenAI 兼容接口。
    :param provider: 不传则使用 Config().llm_provider
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


def _messages_to_openai(messages: Union[List[dict], List[ChatMessage]]) -> List[dict]:
    """统一转为 OpenAI API 的 messages 格式。"""
    out: List[dict] = []
    for m in messages:
        if isinstance(m, ChatMessage):
            out.append(m.to_openai_dict())
        elif isinstance(m, dict) and "role" in m and "content" in m:
            out.append({"role": m["role"], "content": m.get("content") or ""})
        else:
            out.append({"role": "user", "content": str(m)})
    return out


def _parse_tool_calls(raw_message: Any) -> List[ToolCall]:
    """从 API 返回的 message 中解析 tool_calls。"""
    if not raw_message or not getattr(raw_message, "tool_calls", None):
        return []
    result: List[ToolCall] = []
    for tc in raw_message.tool_calls:
        id_ = getattr(tc, "id", None) or ""
        name = (
            getattr(tc, "function", None) and getattr(tc.function, "name", None) or ""
        )
        args = (
            getattr(tc, "function", None)
            and getattr(tc.function, "arguments", None)
            or ""
        )
        result.append(ToolCall(id=id_, name=name, arguments=args))
    return result


class LLMGateway:
    """
    统一 LLM 调用入口：持有一个 provider（或使用默认配置），
    提供异步 chat / chat_with_tools，输入输出使用统一类型。
    """

    def __init__(
        self, provider: Optional[LLMProviderType] = None, model: Optional[str] = None
    ):
        self._provider = provider or Config().llm_provider
        self._client, self._model = get_llm_client_and_model(self._provider)
        if model is not None:
            self._model = model

    @property
    def model(self) -> str:
        return self._model

    @property
    def client(self) -> Any:
        return self._client

    async def chat(
        self,
        messages: Union[List[dict], List[ChatMessage]],
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        model_override: Optional[str] = None,
    ) -> ChatCompletionResult:
        """
        纯文本对话，不传 tools。
        :param max_tokens: 最大输出 token 数
        :param temperature: 温度，默认 0.2
        :param messages: 消息列表，每项为 dict(role, content) 或 ChatMessage
        :param model_override: 临时覆盖本次调用的 model
        """
        openai_messages = _messages_to_openai(messages)
        model = model_override or self._model
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": openai_messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0] if response.choices else None
        if not choice:
            return ChatCompletionResult(content="", raw_message=None)

        msg = choice.message
        content = getattr(msg, "content", None) or ""
        finish = getattr(choice, "finish_reason", None)
        return ChatCompletionResult(
            content=content,
            finish_reason=finish,
            raw_message=msg,
        )

    async def chat_with_tools(
        self,
        messages: Union[List[dict], List[ChatMessage]],
        tools: List[Union[dict, ToolDef]],
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        model_override: Optional[str] = None,
    ) -> ChatCompletionResult:
        """
        带 function calling 的对话；返回 content + tool_calls。
        :param model_override:
        :param max_tokens:
        :param temperature:
        :param messages:
        :param tools: ToolDef 或 OpenAI 格式的 function 定义
        """
        openai_messages = _messages_to_openai(messages)
        openai_tools = []
        for t in tools:
            if isinstance(t, ToolDef):
                openai_tools.append(t.to_openai_dict())
            elif isinstance(t, dict):
                openai_tools.append(t)
            else:
                continue

        model = model_override or self._model
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": openai_messages,
            "tools": openai_tools,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0] if response.choices else None
        if not choice:
            return ChatCompletionResult(content="", tool_calls=[], raw_message=None)

        msg = choice.message
        content = getattr(msg, "content", None) or ""
        tool_calls = _parse_tool_calls(msg)
        finish = getattr(choice, "finish_reason", None)
        return ChatCompletionResult(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish,
            raw_message=msg,
        )
