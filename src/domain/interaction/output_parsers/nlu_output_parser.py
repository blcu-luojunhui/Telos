"""
NLU 输出解析器：将 LLM 返回的 JSON 文本解析为 List[ParsedRecord]。

复用 nlu 子模块的 normalize/validate 逻辑，保持行为一致。
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, List, Optional

from pydantic import Field
from langchain_core.output_parsers import BaseOutputParser

from src.domain.interaction.schemas import IntentType, ParsedRecord
from src.domain.interaction.nlu.normalize_validate import (
    normalize_date,
    normalize_intent,
    normalize_payload,
    validate_payload,
)


class NLUOutputParser(BaseOutputParser[List[ParsedRecord]]):
    """
    解析 LLM 输出的 JSON 文本为 ParsedRecord 列表。

    支持单意图（{"intent": ..., "payload": ...}）
    和多意图（{"intents": [...]}）两种格式。
    """

    reference_date: date = Field(default_factory=date.today)
    preprocess_hints: dict[str, Any] = Field(default_factory=dict)
    raw_message: str = ""

    class Config:
        arbitrary_types_allowed = True

    @property
    def _type(self) -> str:
        return "nlu_output_parser"

    def _extract_json(self, text: str) -> dict:
        t = (text or "").strip()
        if t.startswith("```"):
            lines = t.split("\n")
            t = "\n".join(
                lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            )
            t = t.strip()
        try:
            return json.loads(t)
        except Exception:
            i = t.find("{")
            j = t.rfind("}")
            if i >= 0 and j > i:
                return json.loads(t[i : j + 1])
            return {}

    def _parse_one(self, data: dict) -> ParsedRecord:
        intent = normalize_intent(data.get("intent"))
        parsed_date = normalize_date(
            data.get("date"), self.reference_date, hints=self.preprocess_hints
        )
        payload = normalize_payload(
            intent, data.get("payload"), hints=self.preprocess_hints
        )
        payload, err = validate_payload(intent, payload)
        if err and intent != IntentType.UNKNOWN:
            intent = IntentType.UNKNOWN
            payload = {}
        return ParsedRecord(
            intent=intent,
            date=parsed_date,
            payload=payload,
            raw_message=self.raw_message,
        )

    def parse(self, text: str) -> List[ParsedRecord]:
        data = self._extract_json(text)

        intents_raw = data.get("intents")
        if isinstance(intents_raw, list) and len(intents_raw) > 0:
            out: List[ParsedRecord] = []
            for item in intents_raw:
                if isinstance(item, dict):
                    out.append(self._parse_one(item))
            if out:
                return out

        return [self._parse_one(data)]

    def get_format_instructions(self) -> str:
        return (
            "输出一个 JSON 对象。单意图格式："
            '{"intent": "...", "date": "YYYY-MM-DD 或 null", "payload": {...}}。'
            "多意图格式："
            '{"intents": [{"intent": "...", "date": null, "payload": {...}}, ...]}。'
            "不要 markdown，不要多余说明。"
        )
