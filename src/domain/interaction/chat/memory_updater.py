"""
用户记忆增量更新器：在每次聊天后异步更新用户沟通画像。

fire-and-forget，不阻塞回复。防抖：每 10 条消息最多写一次 DB。
"""

from __future__ import annotations

import logging
from typing import Sequence

from .user_memory import (
    UserMemoryProfile,
    load_user_memory,
    save_user_memory,
    extract_user_signals,
)

logger = logging.getLogger("interaction")

# 防抖：每 N 条消息更新一次
_UPDATE_INTERVAL = 10


async def maybe_update_user_memory(
    user_id: str,
    message: str,
    history: Sequence[dict],
) -> None:
    """
    增量更新用户沟通画像。

    防抖逻辑：只在 msg_count 达到 _UPDATE_INTERVAL 的倍数时写 DB。
    """
    try:
        profile = await load_user_memory(user_id)
        profile.msg_count += 1

        # 防抖：不到间隔不写 DB
        if profile.msg_count % _UPDATE_INTERVAL != 0 and profile.msg_count > 1:
            return

        signals = extract_user_signals(message, list(history))

        # 合并语气
        if signals.get("tone"):
            if not profile.tone:
                profile.tone = signals["tone"]
            elif signals["tone"] == "meme-heavy" and profile.tone != "meme-heavy":
                # 如果用户开始用网络用语，更新
                profile.tone = "meme-heavy"

        # 合并消息长度（取最近的趋势）
        if signals.get("msg_length"):
            profile.avg_msg_length = signals["msg_length"]

        # 合并兴趣
        if signals.get("interests"):
            for interest in signals["interests"]:
                if interest not in profile.interests:
                    profile.interests.append(interest)
            # 最多保留 10 个
            profile.interests = profile.interests[:10]

        # 合并网络用语
        if signals.get("slang"):
            for slang in signals["slang"]:
                if slang not in profile.slang_examples:
                    profile.slang_examples.append(slang)
            # 最多保留 10 个
            profile.slang_examples = profile.slang_examples[:10]

        await save_user_memory(user_id, profile)
        logger.debug(
            "Updated user memory for %s (msg_count=%d)",
            user_id, profile.msg_count,
        )
    except Exception as e:
        logger.debug("Failed to update user memory for %s: %s", user_id, e)
