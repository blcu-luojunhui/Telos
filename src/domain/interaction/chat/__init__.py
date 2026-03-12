"""
Chat 领域：响应模型与展示工具。

用例编排与持久化已迁移至 core.service.ChatApplicationService 与 infra.persistence。
"""

from .response import ChatResponse

__all__ = ["ChatResponse"]
