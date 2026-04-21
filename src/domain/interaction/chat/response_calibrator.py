"""
回复参数校准器：根据用户消息和上下文动态调整回复策略。

不调用 LLM，纯关键词/长度检测，快速返回配置。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass
class ResponseConfig:
    """回复配置"""
    temperature: float = 0.55
    max_tokens: int = 380
    response_hint: str = ""


# 情绪关键词
EMOTIONAL_KEYWORDS = {
    "累", "烦", "难受", "痛苦", "焦虑", "压力", "崩溃", "抑郁",
    "开心", "高兴", "兴奋", "激动", "爽", "舒服", "满足",
    "生气", "愤怒", "火大", "气死", "烦躁",
    "害怕", "担心", "紧张", "慌", "怕",
}

# 问题关键词
QUESTION_KEYWORDS = {
    "怎么", "如何", "为什么", "什么", "哪", "能不能", "可以吗",
    "是不是", "对不对", "好不好", "行不行", "？", "?",
}


def calibrate_response(
    message: str,
    history: Sequence[dict],
    user_memory: Optional[any] = None,
) -> ResponseConfig:
    """
    根据用户消息和上下文校准回复参数。

    :param message: 用户当前消息
    :param history: 对话历史
    :param user_memory: 用户记忆画像（可选）
    :return: ResponseConfig
    """
    msg = message.strip()
    msg_len = len(msg)

    # 默认配置
    config = ResponseConfig(
        temperature=0.55,
        max_tokens=380,
        response_hint="",
    )

    # 用户消息很短（< 5 字）：简短回应
    if msg_len < 5:
        config.max_tokens = 150
        config.temperature = 0.6
        config.response_hint = "用户回复很简短，你也简短回应即可，1-2句话。"
        return config

    # 用户消息很长（> 50 字）或含情绪词：认真回应
    has_emotion = any(kw in msg for kw in EMOTIONAL_KEYWORDS)
    if msg_len > 50 or has_emotion:
        config.max_tokens = 500
        config.temperature = 0.5
        if has_emotion:
            config.response_hint = "用户在倾诉或表达情绪，先共情再回应，不要急着给建议。"
        else:
            config.response_hint = "用户说了很多，认真回应，可以稍长一些，3-5句。"
        return config

    # 用户在问问题
    has_question = any(kw in msg for kw in QUESTION_KEYWORDS)
    if has_question:
        config.max_tokens = 400
        config.response_hint = "用户在问问题，给出具体有用的回答。"
        return config

    # 根据用户记忆调整
    if user_memory and hasattr(user_memory, "avg_msg_length"):
        if user_memory.avg_msg_length == "short":
            config.max_tokens = int(config.max_tokens * 0.7)
            config.response_hint = "这位用户偏好简短回复。"

    return config
