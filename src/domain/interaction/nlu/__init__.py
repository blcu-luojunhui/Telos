"""
NLU 入口（LangChain 版）。

parse_user_message 使用 LangChain LCEL chain 实现。
preprocess、normalize_validate 等工具函数为本模块内的实际代码。
"""
from src.domain.interaction.chains.nlu_chain import parse_user_message
from .preprocess import preprocess_message, PreprocessResult

__all__ = ["parse_user_message", "preprocess_message", "PreprocessResult"]
