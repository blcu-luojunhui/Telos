"""
小聊天链：当 NLU 未识别到结构化记录意图时，生成自然语言回复。

使用 LangChain Agent + Tools 替代原有的 ReActAgent。
支持微信搜索工具调用、人格注入。
"""

from __future__ import annotations

from typing import Optional, Sequence

from langchain_core.tools import StructuredTool

from src.domain.interaction.chat.stickers import parse_sticker_from_reply
from ..llm import get_chat_model
from ..prompts.chat import build_chat_prompt


def _format_history(history: Sequence[dict]) -> str:
    lines: list[str] = []
    for turn in history[-10:]:
        role = str(turn.get("role") or "").strip()
        content = str(turn.get("content") or "").strip()
        if not content or role not in {"user", "assistant"}:
            continue
        prefix = "用户" if role == "user" else "助手"
        if len(content) > 120:
            content = content[:120] + "…"
        lines.append(f"{prefix}：{content}")
    return "\n".join(lines) if lines else "（暂无历史）"


def _build_weixin_search_tool() -> Optional[StructuredTool]:
    """尝试构建微信搜索 LangChain Tool，失败则返回 None。"""
    try:
        from src.infra.tools import build_wechat_search_tool

        wechat_tool = build_wechat_search_tool()

        return StructuredTool.from_function(
            func=wechat_tool.execute,
            name="weixin_search",
            description="搜索微信公众号文章。输入搜索关键词，返回相关文章摘要。",
        )
    except Exception:
        return None


async def small_chat_reply(
    user_id: str,
    message: str,
    history: Sequence[dict],
    soul_id: Optional[str] = None,
) -> tuple[str, Optional[int]]:
    """
    当 NLU 未识别出结构化记录意图时，基于历史上下文给出自然语言回复。

    :param user_id: 用户 ID
    :param message: 用户输入
    :param history: 对话历史
    :param soul_id: 可选人格 slug
    :return: (回复正文, sticker_id 或 None)
    """
    history_block = _format_history(history)
    chat_prompt = await build_chat_prompt(soul_id)

    chain_input = {
        "user_id": user_id,
        "history_block": history_block,
        "message": message.strip(),
    }

    weixin_tool = _build_weixin_search_tool()
    raw: Optional[str] = None

    if weixin_tool:
        try:
            from langchain.agents import AgentExecutor, create_tool_calling_agent

            llm = get_chat_model(temperature=0.4, max_tokens=200)
            tools = [weixin_tool]

            agent = create_tool_calling_agent(llm, tools, chat_prompt)
            executor = AgentExecutor(
                agent=agent,
                tools=tools,
                max_iterations=4,
                handle_parsing_errors=True,
            )
            result = await executor.ainvoke(chain_input)
            raw = (result.get("output") or "").strip()
        except Exception:
            raw = None

    if not raw:
        llm = get_chat_model(temperature=0.4, max_tokens=200)
        result = await (chat_prompt | llm).ainvoke(chain_input)
        raw = (result.content or "").strip()

    if not raw:
        raw = "我在听，你可以再多说一点，或者告诉我想记录今天的饮食、运动或身体数据。"

    reply_text, sticker_id = parse_sticker_from_reply(raw)
    reply_text = reply_text or raw
    return (reply_text.strip(), sticker_id)
