"""
Agent 工具：统一抽象（Tool / ToolExecutor）与具体工具实现。
"""

from src.infra.tools.base import Tool, ToolExecutor, ToolFn
from src.infra.tools.wechat_search import build_wechat_search_tool

__all__ = [
    "Tool",
    "ToolFn",
    "ToolExecutor",
    "build_wechat_search_tool",
]
