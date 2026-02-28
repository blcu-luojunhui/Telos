"""
Chat 包：带上下文的对话管理 + 重复检测 + 确认流程。
"""
from .handler import handle_chat_message
from .response import ChatResponse
from .session import ChatSession, get_or_create_session

__all__ = [
    "handle_chat_message",
    "ChatResponse",
    "ChatSession",
    "get_or_create_session",
]
