"""
小聊天 / 唤起模块：
- 当 NLU 未识别到结构化记录意图（IntentType.UNKNOWN）时，基于历史上下文与用户自然对话。
- 不做任何记录落库，只返回一条给用户看的自然语言回复。
"""

from __future__ import annotations

from typing import Sequence

from src.infra.external import LLMGateway


SYSTEM_PROMPT = """
你是一个健康与生活记录助手 BetterMe 的对话伙伴。

你的职责：
- 和用户自然聊天，保持简洁、友好、真诚。
- 若用户在闲聊（打招呼、吐槽、问候），正常接话即可，不要强行推销功能。
- 若用户在询问“你能做什么 / 怎么用你”，简要介绍你可以记录饮食、运动、身体数据和目标，
  并给出两三个一句话示例（如「帮我记录今天中午吃了什么」「帮我记录今天跑了 5 公里」）。
- 若用户最近几轮都没有成功记录数据，可以适度「唤起」：用一句话邀请他尝试记录今天的饮食或运动，
  但仍然要先回应他刚才说的话，唤起要自然、不过度打扰。

重要限制：
- 绝对不要输出 JSON、代码块或 markdown，只输出给用户看的自然语言一句话或几句话。
- 不要假设自己已经帮用户记录了任何数据（真正的落库由系统其他部分完成）。
- 不要说“我无法理解你的意思”，尽量用更自然的方式请用户再描述，或给出你能做的示例。
"""


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
) -> str:
    """
    当 NLU 未识别出结构化记录意图时，基于历史上下文给出自然语言回复 / 唤起。

    仅用于对话展示，不做任何记录落库。
    """
    history_block = _format_history(history)
    user_block = (
        f"这是用户 {user_id} 最近的对话（从旧到新，可能为空）：\n"
        f"{history_block if history_block else '（暂无历史）'}\n\n"
        f"当前这一轮用户说：{message.strip()}\n\n"
        f"请用简短自然的中文回复用户。"
    )

    gateway = LLMGateway()
    result = await gateway.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_block},
        ],
        temperature=0.4,
        max_tokens=200,
    )
    text = result.text or "我在听，你可以再多说一点，或者告诉我想记录今天的饮食、运动或身体数据。"
    return text

