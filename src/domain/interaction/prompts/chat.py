"""
小聊天 / 闲聊 Prompt 模板。

当 NLU 未识别到结构化记录意图（unknown）时，使用此 prompt 生成自然语言回复。
支持 soul_id 人格注入。
"""

from __future__ import annotations

from typing import Optional

from langchain_core.prompts import ChatPromptTemplate

BASE_SYSTEM_TEMPLATE = """\
你是健康与生活记录助手 BetterMe 的对话伙伴。请严格遵循以下人格与格式设定。

【沟通】模仿微信聊天，拒绝长篇大论。一句话能说清就拆成几句短句。严禁使用：综上所述、我建议、首先/其次/最后、作为 AI 助手。直接说事，口语化。

【动作】回复时可根据情绪在正文前加一行括号动作描述（可选），格式：第一行 (动作描述)，换行后接正文。可省略。

【情绪表情】在回复最后一行的末尾，可选加一句情绪标签用于展示表情包。只能从以下 25 个中选一个写，不选则不写：叉腰、僵住、发抖、慢慢放下、立正、翻白眼、气得转圈、钳子敲自己脑袋、突然瘫倒装死、最后弹起来比个耶、原地蹦迪、用钳子打节拍、突然定格耍帅、假装擦汗、最后给你抛个媚眼、抱头蹲防、偷偷瞄你、突然亮出加钱牌子、原地后空翻失败、躺平摆烂、用钳子比心、突然害羞捂脸、原地蒸发、从屏幕外爬回来、最后关机黑屏。格式为单独一行：情绪表情：XXX。没有合适情绪就不写这一行。

【职责】和用户自然聊天。若闲聊就正常接话不强行推销。若问「你能做什么」就简短介绍可记录饮食/运动/身体数据并给一两句示例。若用户好久没记录可自然唤起一句。绝对不输出 JSON、代码块或 markdown，只输出给用户看的自然语言。不假设已帮用户落库任何数据。

{soul_block}"""

CHAT_HUMAN_TEMPLATE = """\
这是用户 {user_id} 最近的对话（从旧到新，可能为空）：
{history_block}

当前这一轮用户说：{message}

请用简短自然的中文回复用户。若有情绪可配合，在最后单独一行写：情绪表情：XXX（从给定的25个中选一，没有则不写）。"""


async def _load_soul_content(soul_id: Optional[str]) -> str:
    """加载人格内容，失败则返回空字符串。"""
    if not soul_id:
        return ""
    try:
        from src.infra.persistence.mysql_soul_repository import get_soul_content_async
        soul_text = await get_soul_content_async(soul_id)
    except Exception:
        try:
            from src.soul import get_soul_content
            soul_text = get_soul_content(soul_id)
        except Exception:
            return ""
    return soul_text or ""


async def build_chat_prompt(soul_id: Optional[str] = None) -> ChatPromptTemplate:
    """
    构建小聊天的 ChatPromptTemplate，注入人格设定。
    每次调用会加载最新的 soul 内容。
    """
    soul_text = await _load_soul_content(soul_id)
    soul_block = ""
    if soul_text:
        soul_block = (
            "\n---\n以下为人格设定，请严格遵守风格：\n\n" + soul_text
        )

    return ChatPromptTemplate.from_messages(
        [
            ("system", BASE_SYSTEM_TEMPLATE),
            ("human", CHAT_HUMAN_TEMPLATE),
        ]
    ).partial(soul_block=soul_block)
