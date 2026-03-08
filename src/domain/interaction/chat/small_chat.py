"""
小聊天 / 唤起模块：
- 当 NLU 未识别到结构化记录意图（IntentType.UNKNOWN）时，基于历史上下文与用户自然对话。
- 人格由 soul 注册表按 soul_id 注入（见 src.soul），前端可筛选切换。
"""

from __future__ import annotations

from typing import Sequence

from src.infra.external import LLMGateway
from src.infra.tools import ToolExecutor, build_wechat_search_tool
from src.core.agents import ReActAgent
from .stickers import parse_sticker_from_reply


# 与人格无关的通用规则（格式、情绪表情、职责）
_BASE_SYSTEM_PROMPT = """
你是健康与生活记录助手 BetterMe 的对话伙伴。请严格遵循以下人格与格式设定。

【沟通】模仿微信聊天，拒绝长篇大论。一句话能说清就拆成几句短句。严禁使用：综上所述、我建议、首先/其次/最后、作为 AI 助手。直接说事，口语化。

【动作】回复时可根据情绪在正文前加一行括号动作描述（可选），格式：第一行 (动作描述)，换行后接正文。可省略。

【情绪表情】在回复最后一行的末尾，可选加一句情绪标签用于展示表情包。只能从以下 25 个中选一个写，不选则不写：叉腰、僵住、发抖、慢慢放下、立正、翻白眼、气得转圈、钳子敲自己脑袋、突然瘫倒装死、最后弹起来比个耶、原地蹦迪、用钳子打节拍、突然定格耍帅、假装擦汗、最后给你抛个媚眼、抱头蹲防、偷偷瞄你、突然亮出加钱牌子、原地后空翻失败、躺平摆烂、用钳子比心、突然害羞捂脸、原地蒸发、从屏幕外爬回来、最后关机黑屏。格式为单独一行：情绪表情：XXX。没有合适情绪就不写这一行。

【职责】和用户自然聊天。若闲聊就正常接话不强行推销。若问「你能做什么」就简短介绍可记录饮食/运动/身体数据并给一两句示例。若用户好久没记录可自然唤起一句。绝对不输出 JSON、代码块或 markdown，只输出给用户看的自然语言。不假设已帮用户落库任何数据。
"""


async def _build_system_prompt(soul_id: str | None) -> str:
    """根据 soul_id（slug）拼出完整 system prompt：通用 base + 该人格内容（优先 DB）。"""
    try:
        from src.infra.persistence.mysql_soul_repository import get_soul_content_async
        soul_text = await get_soul_content_async(soul_id)
    except Exception:
        from src.soul import get_soul_content
        soul_text = get_soul_content(soul_id)
    if not soul_text:
        return _BASE_SYSTEM_PROMPT
    return (
        _BASE_SYSTEM_PROMPT
        + "\n\n---\n以下为人格设定，请严格遵守风格：\n\n"
        + soul_text
    )


# 带「微信搜索」工具的 ReAct Agent（供 small_chat 使用）
_WEIXIN_TOOLS_EXECUTOR = ToolExecutor([build_wechat_search_tool()])
_WEIXIN_REACT_AGENT = ReActAgent(tool_executor=_WEIXIN_TOOLS_EXECUTOR, max_steps=4)


def _format_history(history: Sequence[dict]) -> str:
    """把最近若干条 user/assistant 消息格式化成简短对话文本。"""
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
    return "\n".join(lines)


async def small_chat_reply(
    user_id: str,
    message: str,
    history: Sequence[dict],
    soul_id: str | None = None,
) -> tuple[str, int | None]:
    """
    当 NLU 未识别出结构化记录意图时，基于历史上下文给出自然语言回复 / 唤起。

    soul_id：可选人格 slug（见 souls 表），不传则用默认（如 rude）。仅用于对话展示，不做任何记录落库。
    返回 (回复正文, sticker_id 或 None)。
    """
    system_prompt = await _build_system_prompt(soul_id)
    history_block = _format_history(history)
    user_block = (
        f"这是用户 {user_id} 最近的对话（从旧到新，可能为空）：\n"
        f"{history_block if history_block else '（暂无历史）'}\n\n"
        f"当前这一轮用户说：{message.strip()}\n\n"
        f"请用简短自然的中文回复用户。若有情绪可配合，在最后单独一行写：情绪表情：XXX（从给定的25个中选一，没有则不写）。"
    )
    react_question = (
        "下面是小聊天的任务说明、人格设定以及对话上下文，请严格遵守人格与沟通风格要求：\n\n"
        f"{system_prompt}\n\n"
        f"{user_block}\n\n"
        "如果需要从微信生态（例如公众号文章等）检索信息辅助回答，请调用 weixin_search[关键词] 或 "
        "weixin_search[关键词|页码] 工具；如果不需要外部搜索，就直接根据现有信息回答，并使用 Finish[给用户看的最终回复] 结束。"
    )

    raw: str | None = None
    try:
        react_result = await _WEIXIN_REACT_AGENT.run(react_question)
        if react_result.success and (react_result.final_answer or "").strip():
            raw = (react_result.final_answer or "").strip()
    except Exception:
        raw = None

    if not raw:
        gateway = LLMGateway()
        result = await gateway.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_block},
            ],
            temperature=0.4,
            max_tokens=200,
        )
        raw = (
            result.text
            or "我在听，你可以再多说一点，或者告诉我想记录今天的饮食、运动或身体数据。"
        )
    reply_text, sticker_id = parse_sticker_from_reply(raw)
    reply_text = reply_text or raw
    return (reply_text.strip(), sticker_id)

