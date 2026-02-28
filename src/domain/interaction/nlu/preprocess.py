"""
Stage 0: 确定性预处理（Hybrid NLU）。

目标：
- 从原始文本中提取“高置信提示”（日期/餐次/运动类型/单位换算线索）
- 生成一份更适合抽取的 normalized_text（不改语义，只做轻量归一）
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re
from typing import Any


@dataclass(frozen=True)
class PreprocessResult:
    normalized_text: str
    hints: dict[str, Any]


_RE_ISO_DATE = re.compile(r"\b(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})\b")
_RE_CN_MD = re.compile(r"(?<!\d)(\d{1,2})月(\d{1,2})日(?!\d)")
_RE_JIN = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*斤")
_RE_METER = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*(?:m|米)\b", re.IGNORECASE)
_RE_KM = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*(?:km|公里)\b", re.IGNORECASE)
_RE_K = re.compile(r"\b(?P<num>\d+(?:\.\d+)?)\s*k\b", re.IGNORECASE)
_RE_MIN = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*(?:min|分钟)\b", re.IGNORECASE)
_RE_HOUR = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*(?:h|小时)\b", re.IGNORECASE)
_RE_HALF_HOUR = re.compile(r"半\s*小时")


def _safe_float(s: str) -> float | None:
    try:
        return float(s)
    except Exception:
        return None


def _detect_explicit_date(text: str, reference_date: date) -> date | None:
    m = _RE_ISO_DATE.search(text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d)
        except ValueError:
            return None

    m = _RE_CN_MD.search(text)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        try:
            return date(reference_date.year, mo, d)
        except ValueError:
            return None

    # 常见相对日期
    if "今天" in text or "today" in text.lower():
        return reference_date
    if "昨天" in text or "yesterday" in text.lower():
        return reference_date - timedelta(days=1)
    if "前天" in text:
        return reference_date - timedelta(days=2)
    return None


def _hint_meal_type(text: str) -> str | None:
    t = text.lower()
    if any(k in text for k in ("早餐", "早饭")) or "breakfast" in t:
        return "breakfast"
    if any(k in text for k in ("午餐", "午饭", "中午饭", "中饭")) or "lunch" in t:
        return "lunch"
    if any(k in text for k in ("晚餐", "晚饭", "晚饭吃", "晚饭了")) or "dinner" in t:
        return "dinner"
    if any(k in text for k in ("加餐", "零食", "夜宵")) or any(k in t for k in ("snack", "late-night")):
        return "snack"
    return None


def _hint_workout_type(text: str) -> str | None:
    t = text.lower()
    if any(k in text for k in ("跑步", "慢跑", "长跑", "夜跑", "晨跑")) or "run" in t or "jog" in t:
        return "run"
    if "篮球" in text or "basketball" in t:
        return "basketball"
    if any(k in text for k in ("力量", "撸铁", "健身", "举铁", "深蹲", "卧推", "硬拉")) or "strength" in t or "gym" in t:
        return "strength"
    return None


def _normalize_distance(text: str) -> tuple[str, float | None]:
    # 5000m / 5000米 -> 5 km（保留 1-3 位小数）
    m = _RE_METER.search(text)
    if m:
        v = _safe_float(m.group("num"))
        if v is not None and v >= 100:
            km = round(v / 1000.0, 3)
            text = _RE_METER.sub(f"{km} km", text, count=1)
            return text, km

    # 5k -> 5 km
    m = _RE_K.search(text)
    if m:
        v = _safe_float(m.group("num"))
        if v is not None:
            text = _RE_K.sub(f"{v} km", text, count=1)
            return text, float(v)

    m = _RE_KM.search(text)
    if m:
        v = _safe_float(m.group("num"))
        if v is not None:
            return text, float(v)

    return text, None


def _normalize_duration(text: str) -> tuple[str, int | None]:
    # 半小时 -> 30 min
    if _RE_HALF_HOUR.search(text):
        text = _RE_HALF_HOUR.sub("30 min", text, count=1)
        return text, 30

    m = _RE_HOUR.search(text)
    if m:
        v = _safe_float(m.group("num"))
        if v is not None:
            minutes = int(round(v * 60))
            text = _RE_HOUR.sub(f"{minutes} min", text, count=1)
            return text, minutes

    m = _RE_MIN.search(text)
    if m:
        v = _safe_float(m.group("num"))
        if v is not None:
            return text, int(round(v))

    return text, None


def _normalize_weight(text: str) -> tuple[str, float | None]:
    # 斤 -> kg（1 斤=0.5kg）
    m = _RE_JIN.search(text)
    if not m:
        return text, None
    v = _safe_float(m.group("num"))
    if v is None:
        return text, None
    kg = round(v * 0.5, 3)
    text = _RE_JIN.sub(f"{kg} kg", text, count=1)
    return text, kg


def preprocess_message(message: str, reference_date: date) -> PreprocessResult:
    text = (message or "").strip()
    # 轻量统一空白
    text = re.sub(r"\s+", " ", text)

    explicit_date = _detect_explicit_date(text, reference_date)
    meal_type = _hint_meal_type(text)
    workout_type = _hint_workout_type(text)

    normalized = text
    normalized, distance_km = _normalize_distance(normalized)
    normalized, duration_min = _normalize_duration(normalized)
    normalized, weight_kg = _normalize_weight(normalized)

    hints: dict[str, Any] = {
        "explicit_date": explicit_date.isoformat() if explicit_date else None,
        "meal_type": meal_type,
        "workout_type": workout_type,
        "distance_km": distance_km,
        "duration_min": duration_min,
        "weight_kg": weight_kg,
    }
    # 只保留非空提示，避免噪声
    hints = {k: v for k, v in hints.items() if v is not None}

    return PreprocessResult(normalized_text=normalized, hints=hints)

