"""
LangChain 回调：记录交互链的执行过程，用于调试与审计。

通过 LangChain 的 CallbackHandler 机制，在 chain/agent 运行时
自动记录 LLM 调用、Token 使用、错误等信息。
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger("interaction")


class InteractionCallbackHandler(AsyncCallbackHandler):
    """
    交互层 LangChain 回调：记录 LLM 调用开始/结束、token 用量、错误。
    可挂载到任意 chain/agent 的 callbacks 参数上。
    """

    def __init__(self, trace_id: Optional[str] = None):
        super().__init__()
        self.trace_id = trace_id or "unknown"
        self.total_tokens = 0
        self.total_cost = 0.0

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        model = serialized.get("kwargs", {}).get("model_name", "unknown")
        logger.debug(
            "[%s] LLM start | model=%s | prompts=%d",
            self.trace_id,
            model,
            len(prompts),
        )

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        token_usage = {}
        if response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})
        total = token_usage.get("total_tokens", 0)
        self.total_tokens += total
        logger.debug(
            "[%s] LLM end | tokens=%d (cumulative=%d)",
            self.trace_id,
            total,
            self.total_tokens,
        )

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        logger.error(
            "[%s] LLM error: %s",
            self.trace_id,
            str(error),
            exc_info=True,
        )

    async def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        id_field = serialized.get("id", ["unknown"])
        chain_name = serialized.get("name") or (
            id_field[-1] if isinstance(id_field, list) else str(id_field)
        )
        logger.debug("[%s] Chain start: %s", self.trace_id, chain_name)

    async def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        logger.debug("[%s] Chain end", self.trace_id)

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        tool_name = serialized.get("name", "unknown")
        logger.debug("[%s] Tool start: %s", self.trace_id, tool_name)

    async def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        logger.debug("[%s] Tool end", self.trace_id)
