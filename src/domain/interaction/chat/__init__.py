"""
Chat 包：基于 user_id 的持久化对话管理 + 重复检测 + 确认流程。
"""

from .handler import handle_chat_message
from .response import ChatResponse
from .session import (
    UserSession,
    get_user_session,
    get_or_create_conversation,
)

__all__ = [
    "handle_chat_message",
    "ChatResponse",
    "UserSession",
    "get_user_session",
    "get_or_create_conversation",
]
