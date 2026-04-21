"""
用户沟通记忆：记住用户的说话风格、兴趣点和偏好。

基于 UserPreference.communication_preferences_json 列存储，
不新增数据库表。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional

# 网络用语检测模式
_SLANG_PATTERNS = [
    "hh", "hhh", "hhhh", "哈哈", "哈哈哈", "笑死", "绝了", "6666",
    "yyds", "awsl", "xswl", "nbcs", "破防", "蚌埠住", "离谱",
    "好家伙", "真的会谢", "DNA动了", "格局", "绝绝子", "属实",
    "裂开", "麻了", "无语", "救命", "芭比Q",
]

# 兴趣话题关键词
_INTEREST_KEYWORDS = {
    "跑步": ["跑", "配速", "公里", "km", "马拉松", "半马", "全马", "LSD"],
    "篮球": ["篮球", "投篮", "三分", "NBA", "打球"],
    "健身": ["力量", "深蹲", "卧推", "硬拉", "增肌", "撸铁"],
    "减脂": ["减脂", "减肥", "瘦", "体脂", "热量", "卡路里"],
    "饮食": ["吃", "火锅", "烧烤", "外卖", "做饭", "食谱"],
    "睡眠": ["睡", "失眠", "早起", "熬夜", "作息"],
    "工作": ["加班", "工作", "开会", "项目", "deadline"],
    "读书": ["读书", "看书", "阅读", "书单"],
}


@dataclass
class UserMemoryProfile:
    """用户沟通画像"""
    tone: str = ""                                  # casual / formal / meme-heavy
    avg_msg_length: str = ""                        # short / medium / long
    interests: list[str] = field(default_factory=list)
    sensitive_topics: list[str] = field(default_factory=list)
    slang_examples: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    msg_count: int = 0                              # 已分析的消息数


async def load_user_memory(user_id: str) -> UserMemoryProfile:
    """从 user_preferences.communication_preferences_json 加载用户画像。"""
    try:
        from sqlalchemy import select
        from src.infra.database.mysql import async_mysql_pool
        from src.infra.database.mysql.models_v2 import UserPreference
        from src.infra.persistence.mysql_user_identity import get_or_create_user_id

        uid = await get_or_create_user_id(user_id)
        async with async_mysql_pool.session() as session:
            r = await session.execute(
                select(UserPreference.communication_preferences_json)
                .where(UserPreference.user_id == uid)
            )
            row = r.scalar_one_or_none()
            if row and isinstance(row, dict):
                return UserMemoryProfile(
                    tone=row.get("tone", ""),
                    avg_msg_length=row.get("avg_msg_length", ""),
                    interests=row.get("interests", []),
                    sensitive_topics=row.get("sensitive_topics", []),
                    slang_examples=row.get("slang_examples", []),
                    notes=row.get("notes", []),
                    msg_count=row.get("msg_count", 0),
                )
    except Exception:
        pass
    return UserMemoryProfile()


async def save_user_memory(user_id: str, profile: UserMemoryProfile) -> None:
    """写入 user_preferences.communication_preferences_json。"""
    try:
        from sqlalchemy import select, update
        from src.infra.database.mysql import async_mysql_pool
        from src.infra.database.mysql.models_v2 import UserPreference
        from src.infra.persistence.mysql_user_identity import get_or_create_user_id

        uid = await get_or_create_user_id(user_id)
        data = asdict(profile)

        async with async_mysql_pool.session() as session:
            r = await session.execute(
                select(UserPreference.id).where(UserPreference.user_id == uid)
            )
            existing = r.scalar_one_or_none()
            if existing:
                await session.execute(
                    update(UserPreference)
                    .where(UserPreference.user_id == uid)
                    .values(communication_preferences_json=data)
                )
            else:
                session.add(UserPreference(
                    user_id=uid,
                    communication_preferences_json=data,
                ))
            await session.commit()
    except Exception:
        pass


def format_memory_for_prompt(profile: UserMemoryProfile) -> str:
    """将用户画像转为自然语言，注入 prompt。"""
    if not profile or profile.msg_count < 3:
        return ""

    parts: list[str] = []

    if profile.tone:
        tone_desc = {
            "casual": "说话比较随意口语化",
            "formal": "说话偏正式",
            "meme-heavy": "经常用网络用语和梗",
        }.get(profile.tone, "")
        if tone_desc:
            parts.append(tone_desc)

    if profile.avg_msg_length:
        len_desc = {
            "short": "习惯发短消息",
            "medium": "消息长度适中",
            "long": "喜欢发长消息详细描述",
        }.get(profile.avg_msg_length, "")
        if len_desc:
            parts.append(len_desc)

    if profile.interests:
        parts.append(f"感兴趣的话题：{'、'.join(profile.interests[:5])}")

    if profile.slang_examples:
        parts.append(f"常用的表达：{'、'.join(profile.slang_examples[:5])}")

    if profile.sensitive_topics:
        parts.append(f"不太想聊的话题：{'、'.join(profile.sensitive_topics[:3])}")

    return "；".join(parts) + "。" if parts else ""


def extract_user_signals(message: str, history: list[dict]) -> dict:
    """
    轻量分析用户消息特征，不调用 LLM。

    返回 dict 包含检测到的信号。
    """
    signals: dict = {}
    msg = message.strip()

    # 消息长度
    msg_len = len(msg)
    if msg_len < 10:
        signals["msg_length"] = "short"
    elif msg_len > 50:
        signals["msg_length"] = "long"
    else:
        signals["msg_length"] = "medium"

    # 网络用语检测
    found_slang: list[str] = []
    msg_lower = msg.lower()
    for slang in _SLANG_PATTERNS:
        if slang.lower() in msg_lower:
            found_slang.append(slang)
    if found_slang:
        signals["slang"] = found_slang

    # 兴趣话题检测
    found_interests: list[str] = []
    for topic, keywords in _INTEREST_KEYWORDS.items():
        if any(kw in msg for kw in keywords):
            found_interests.append(topic)
    if found_interests:
        signals["interests"] = found_interests

    # 语气检测
    if len(found_slang) >= 2 or any(s in msg_lower for s in ["hh", "hhh", "笑死", "绝了"]):
        signals["tone"] = "meme-heavy"
    elif msg_len > 30 and not found_slang:
        signals["tone"] = "formal"
    else:
        signals["tone"] = "casual"

    return signals
