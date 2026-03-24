"""
NLU 解析链：用户自然语言 → List[ParsedRecord]。

流程：preprocess → prompt → LLM → parse → validate（失败则 repair → 重新 parse）

使用 LCEL（LangChain Expression Language）构建链式调用。
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, List, Optional, Sequence

from src.domain.interaction.schemas import IntentType, ParsedRecord
from src.domain.interaction.nlu.preprocess import preprocess_message
from src.domain.interaction.nlu.normalize_validate import (
    normalize_date,
    normalize_intent,
    normalize_payload,
    validate_payload,
)
from ..callbacks import InteractionCallbackHandler
from ..llm import get_chat_model
from ..prompts.nlu import nlu_prompt
from ..prompts.repair import repair_prompt
from ..output_parsers import NLUOutputParser


def _build_history_block(history: Optional[Sequence[dict]]) -> str:
    if not history:
        return ""
    lines: list[str] = []
    for turn in history:
        role = str(turn.get("role") or "").strip() or "user"
        content = str(turn.get("content") or "").strip()
        if not content:
            continue
        if len(content) > 200:
            content = content[:200] + "…"
        lines.append(f"{role}: {content}")
    if not lines:
        return ""
    return (
        "对话历史（从旧到新，最多最近若干条）：\n"
        + "\n".join(lines)
        + "\n\n"
    )


async def parse_user_message(
    message: str,
    reference_date: Optional[date] = None,
    history: Optional[Sequence[dict]] = None,
    trace_id: Optional[str] = None,
    metrics: Optional[dict[str, Any]] = None,
) -> List[ParsedRecord]:
    """
    将用户自然语言解析为结构化记录，支持一句话多意图。

    :param message: 用户输入
    :param reference_date: 若用户未说日期，用此日期（默认今天）
    :param history: 对话历史
    :return: List[ParsedRecord]
    """
    ref = reference_date or date.today()
    ref_str = ref.isoformat()

    pre = preprocess_message(message, ref)
    history_block = _build_history_block(history)

    chain_input = {
        "reference_date": ref_str,
        "hints_json": json.dumps(pre.hints, ensure_ascii=False),
        "history_block": history_block,
        "raw_message": message.strip(),
        "normalized_text": pre.normalized_text,
    }

    cb = InteractionCallbackHandler(trace_id=trace_id or "nlu_parse")
    nlu_chain = nlu_prompt | get_chat_model(temperature=0.1)
    result = await nlu_chain.ainvoke(chain_input, config={"callbacks": [cb]})
    text = result.content or "{}"

    if metrics is not None:
        # 记录 NLU 主链的 token 与费用信息
        metrics["nlu"] = cb.summary()

    parser = NLUOutputParser(
        reference_date=ref,
        preprocess_hints=pre.hints,
        raw_message=message.strip(),
    )

    records = parser.parse(text)

    if not any(r.intent == IntentType.UNKNOWN for r in records):
        return records

    data = parser._extract_json(text)
    if data.get("intents"):
        return records

    intent = normalize_intent(data.get("intent"))
    parsed_date = normalize_date(data.get("date"), ref, hints=pre.hints)
    payload = normalize_payload(intent, data.get("payload"), hints=pre.hints)
    _, err = validate_payload(intent, payload)

    if not err:
        return records

    repair_input = {
        "reference_date": ref_str,
        "raw_message": message.strip(),
        "hints_json": json.dumps(pre.hints, ensure_ascii=False),
        "current_json": json.dumps(
            {
                "intent": intent.value,
                "date": parsed_date.isoformat(),
                "payload": payload,
            },
            ensure_ascii=False,
        ),
        "validation_error": err,
    }

    repair_cb = InteractionCallbackHandler(trace_id=trace_id or "nlu_repair")
    repair = repair_prompt | get_chat_model(temperature=0.0)
    repair_result = await repair.ainvoke(repair_input, config={"callbacks": [repair_cb]})
    repair_text = repair_result.content or "{}"

    if metrics is not None:
        # 记录 repair 链的 token 与费用信息
        metrics["nlu_repair"] = repair_cb.summary()

    repair_parser = NLUOutputParser(
        reference_date=ref,
        preprocess_hints=pre.hints,
        raw_message=message.strip(),
    )
    repaired = repair_parser.parse(repair_text)

    still_broken = all(r.intent == IntentType.UNKNOWN for r in repaired)
    if still_broken and intent != IntentType.UNKNOWN:
        return [
            ParsedRecord(
                intent=IntentType.UNKNOWN,
                date=parsed_date,
                payload={},
                raw_message=message.strip(),
            )
        ]
    return repaired
