"""
LangChain 回调：记录交互链的执行过程，用于调试与审计。

通过 LangChain 的 CallbackHandler 机制，在 chain/agent 运行时
自动记录 LLM 调用、Token 使用、耗时、错误等信息。

日志级别说明：
- DEBUG: 每步 chain/LLM/tool 的开始/结束详情
- INFO:  整次交互结束后的结构化摘要（tokens, latency, steps）
- ERROR: LLM/tool 异常
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger("interaction")


class InteractionCallbackHandler(AsyncCallbackHandler):
    """
    交互层 LangChain 回调：记录 LLM 调用开始/结束、token 用量、耗时、错误。
    可挂载到任意 chain/agent 的 callbacks 参数上。

    使用后可通过 .summary() 获取结构化的统计信息。
    """

    def __init__(self, trace_id: Optional[str] = None):
        super().__init__()
        self.trace_id = trace_id or "unknown"
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.llm_calls = 0
        self.tool_calls = 0
        self.chain_depth = 0
        self._start_time = time.monotonic()
        self._llm_start_times: dict[UUID, float] = {}

    @property
    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._start_time) * 1000)

    def summary(self) -> dict[str, Any]:
        """返回结构化统计信息。"""
        return {
            "trace_id": self.trace_id,
            "elapsed_ms": self.elapsed_ms,
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            # 费用估算不在领域层/回调层做：不同 provider/model 价格差异大，
            # 且部分网关会直接返回更准确的 usage/cost。
            "estimated_cost_usd": None,
        }

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        self.llm_calls += 1
        self._llm_start_times[run_id] = time.monotonic()
        model = "unknown"
        if serialized:
            model = serialized.get("kwargs", {}).get("model_name", "unknown")
        logger.debug(
            "[%s] LLM start #%d | model=%s | prompts=%d",
            self.trace_id, self.llm_calls, model, len(prompts),
        )

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        latency_ms = 0
        start = self._llm_start_times.pop(run_id, None)
        if start is not None:
            latency_ms = int((time.monotonic() - start) * 1000)

        token_usage = {}
        if response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})
        total = token_usage.get("total_tokens", 0)
        prompt = token_usage.get("prompt_tokens", 0)
        completion = token_usage.get("completion_tokens", 0)
        self.total_tokens += total
        self.prompt_tokens += prompt
        self.completion_tokens += completion

        logger.debug(
            "[%s] LLM end | tokens=%d (prompt=%d, completion=%d) | latency=%dms | cumulative=%d",
            self.trace_id, total, prompt, completion, latency_ms, self.total_tokens,
        )

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        self._llm_start_times.pop(run_id, None)
        logger.error(
            "[%s] LLM error: %s", self.trace_id, str(error), exc_info=True,
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
        self.chain_depth += 1
        chain_name = "unknown"
        if serialized:
            id_field = serialized.get("id", ["unknown"])
            chain_name = serialized.get("name") or (
                id_field[-1] if isinstance(id_field, list) else str(id_field)
            )
        logger.debug("[%s] Chain start: %s (depth=%d)", self.trace_id, chain_name, self.chain_depth)

    async def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        self.chain_depth = max(0, self.chain_depth - 1)
        if self.chain_depth == 0:
            s = self.summary()
            logger.info(
                "[%s] Interaction complete | llm_calls=%d | tokens=%d (p=%d c=%d) | tools=%d | %dms",
                s["trace_id"], s["llm_calls"], s["total_tokens"],
                s["prompt_tokens"], s["completion_tokens"],
                s["tool_calls"], s["elapsed_ms"],
            )
        else:
            logger.debug("[%s] Chain end (depth=%d)", self.trace_id, self.chain_depth)

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        self.tool_calls += 1
        tool_name = "unknown"
        if serialized:
            tool_name = serialized.get("name", "unknown")
        logger.debug("[%s] Tool start: %s (#%d)", self.trace_id, tool_name, self.tool_calls)

    async def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        logger.debug("[%s] Tool end", self.trace_id)

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        logger.error(
            "[%s] Tool error: %s", self.trace_id, str(error), exc_info=True,
        )
