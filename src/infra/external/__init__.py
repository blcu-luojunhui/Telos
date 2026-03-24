"""
外部服务封装：LLM 客户端工厂、搜索等。
"""

from .llm import get_llm_client_and_model
from .search import wechat_search

__all__ = [
    "get_llm_client_and_model",
    "wechat_search",
]
