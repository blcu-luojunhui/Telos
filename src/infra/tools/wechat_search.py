"""
微信搜索工具：供 Agent 按关键词（及可选页码）调用微信生态搜索。
"""

from __future__ import annotations

import json
from typing import Any

from src.infra.external.search import wechat_search
from src.infra.tools.base import Tool


async def _execute_search(tool_input: str, **kwargs: Any) -> str:
    """
    工具执行函数。tool_input 格式：「关键词」或「关键词|页码」。
    返回给 LLM 的字符串（JSON 或错误信息）。
    """
    raw = (tool_input or "").strip()
    if not raw:
        return "错误：微信搜索需要提供关键词。用法示例：wechat_search[减脂训练] 或 wechat_search[减脂训练|2]。"

    if "|" in raw:
        keyword, page = [x.strip() for x in raw.split("|", 1)]
        page = page or "1"
    else:
        keyword, page = raw, "1"

    try:
        data = await wechat_search(keyword=keyword, page=page)
    except Exception as e:
        return f"微信搜索调用异常：{e!s}"

    if data is None:
        return "微信搜索没有返回结果。"

    try:
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return f"微信搜索结果序列化失败：{repr(data)[:500]}"


def build_wechat_search_tool() -> Tool:
    """构造名为 wechat_search 的工具，供 ReAct 等 Agent 使用。"""
    return Tool(
        name="wechat_search",
        description=(
            "微信搜索：根据关键词在微信生态（如公众号文章等）中搜索相关内容。"
            "输入格式：关键词 或 关键词|页码，例如 wechat_search[减脂训练] 或 wechat_search[减脂训练|2]。"
        ),
        execute=_execute_search,
    )
