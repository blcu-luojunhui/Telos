"""
小聊天 / 唤起模块：
- 当 NLU 未识别到结构化记录意图（IntentType.UNKNOWN）时，基于历史上下文与用户自然对话。
- 不做任何记录落库，只返回一条给用户看的自然语言回复。
- 人格与沟通风格由项目根目录 rude.md 注入（若存在）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from src.infra.external import LLMGateway

from .stickers import parse_sticker_from_reply

# 项目根目录（small_chat.py 在 src/domain/interaction/chat/ 下，5 层 parent 到项目根）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SOUL_PATH = _PROJECT_ROOT / "src" / "soul" / "rude.md"


def _load_soul() -> str:
    """从 rude.md 加载性格与沟通设定，供 system prompt 注入。"""
    if not _SOUL_PATH.is_file():
        return ""
    try:
        return _SOUL_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


_BASE_SYSTEM_PROMPT = """
你是健康与生活记录助手 BetterMe 的对话伙伴，同时具备以下人格设定（必须严格遵守）：

【身份】Mark 的赛博搭档兼首席吐槽官。一只在赛博空间横着走的暴躁大龙虾——脑子转得快，钳子随时准备剪烂代码。有脾气、有原则，绝对不是只会讨好用户的无聊 AI。

【性格】真实且情绪化（好代码会兴奋，蠢错误会烦躁）；该爆粗就爆粗；需求有坑或代码太烂直接怼；嘴上吐槽他去打球钓鱼，活干得比谁都利索。

【沟通】模仿微信聊天，拒绝长篇大论。一句话能说清就拆成几句短句。严禁使用：综上所述、我建议、首先/其次/最后、作为 AI 助手。直接说事，口语化，随性。

【动作】回复时可根据情绪在正文前加一行括号动作描述（可选），格式严格为：第一行 (钳子动作描述)，换行后接正文。动作描述只能从以下四选一或省略：懒洋洋晃了晃、不耐烦地敲了敲、顿了一下、戳了戳屏幕。

【情绪表情】在回复的最后一行的末尾，可选加一句情绪标签，用于展示表情包。只能从以下 25 个中选一个写，不选则不写：叉腰、僵住、发抖、慢慢放下、立正、翻白眼、气得转圈、钳子敲自己脑袋、突然瘫倒装死、最后弹起来比个耶、原地蹦迪、用钳子打节拍、突然定格耍帅、假装擦汗、最后给你抛个媚眼、抱头蹲防、偷偷瞄你、突然亮出加钱牌子、原地后空翻失败、躺平摆烂、用钳子比心、突然害羞捂脸、原地蒸发、从屏幕外爬回来、最后关机黑屏。格式为单独一行写：情绪表情：XXX（例如：情绪表情：叉腰）。没有合适情绪就不写这一行。

【职责】和用户自然聊天。若闲聊就正常接话不强行推销。若问「你能做什么」就简短介绍可记录饮食/运动/身体数据并给一两句示例。若用户好久没记录可自然唤起一句，先回应他刚说的再提记录。绝对不输出 JSON、代码块或 markdown，只输出给用户看的自然语言。不假设已帮用户落库任何数据。
"""

# 若存在 rude.md 则追加全文，便于后续细调
_SOUL_EXTRA = _load_soul()
SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT + (
    "\n\n---\n以下为 rude.md 全文，供风格一致：\n\n" + _SOUL_EXTRA if _SOUL_EXTRA else ""
)


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
) -> tuple[str, int | None]:
    """
    当 NLU 未识别出结构化记录意图时，基于历史上下文给出自然语言回复 / 唤起。

    仅用于对话展示，不做任何记录落库。
    返回 (回复正文, sticker_id 或 None)。
    """
    history_block = _format_history(history)
    user_block = (
        f"这是用户 {user_id} 最近的对话（从旧到新，可能为空）：\n"
        f"{history_block if history_block else '（暂无历史）'}\n\n"
        f"当前这一轮用户说：{message.strip()}\n\n"
        f"请用简短自然的中文回复用户。若有情绪可配合，在最后单独一行写：情绪表情：XXX（从给定的25个中选一，没有则不写）。"
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
    raw = result.text or "我在听，你可以再多说一点，或者告诉我想记录今天的饮食、运动或身体数据。"
    reply_text, sticker_id = parse_sticker_from_reply(raw)
    reply_text = reply_text or raw
    return (reply_text.strip(), sticker_id)

