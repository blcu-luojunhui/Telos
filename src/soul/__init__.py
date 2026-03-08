"""
Agent Soul：可选人格，供小聊天注入。前端可拉取列表并传 soul_id 切换。
"""

from .registry import list_souls, get_soul_content, default_soul_id, SOULS

__all__ = ["list_souls", "get_soul_content", "default_soul_id", "SOULS"]
