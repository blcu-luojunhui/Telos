"""
Agent Soul 注册表：可选的 Agent 人格，供前端筛选并注入小聊天。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# 注册表：soul_id -> { "name": 展示名, "description": 简短说明, "file": 文件名 }
SOULS: dict[str, dict[str, Any]] = {
    "rude": {
        "name": "暴躁龙虾",
        "description": "有脾气、爱吐槽的赛博大龙虾，嘴硬心软",
        "file": "rude.md",
    },
    "gentle": {
        "name": "温柔小助手",
        "description": "耐心体贴，语气温和，适合需要鼓励时",
        "file": "gentle.md",
    },
    "professional": {
        "name": "专业简洁",
        "description": "简洁专业，不废话，直给结论与建议",
        "file": "professional.md",
    },
    "funny": {
        "name": "幽默搞怪",
        "description": "爱玩梗、接梗，轻松搞笑不冷场",
        "file": "funny.md",
    },
}

_DEFAULT_SOUL_ID = "rude"
_SOUL_DIR: Path | None = None


def _soul_dir() -> Path:
    global _SOUL_DIR
    if _SOUL_DIR is None:
        _SOUL_DIR = Path(__file__).resolve().parent
    return _SOUL_DIR


def list_souls() -> list[dict[str, Any]]:
    """返回可供前端展示的 soul 列表（id、name、description）。"""
    return [
        {"id": sid, "name": info["name"], "description": info.get("description", "")}
        for sid, info in SOULS.items()
    ]


def get_soul_content(soul_id: str | None) -> str:
    """
    根据 soul_id 加载对应人格文档内容；无效或未传则用默认（rude）。
    """
    sid = (soul_id or "").strip().lower() or _DEFAULT_SOUL_ID
    info = SOULS.get(sid)
    if not info:
        sid = _DEFAULT_SOUL_ID
        info = SOULS.get(sid)
    if not info:
        return ""
    path = _soul_dir() / info["file"]
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def default_soul_id() -> str:
    return _DEFAULT_SOUL_ID
