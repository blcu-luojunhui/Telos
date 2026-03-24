"""
NLU 入口（LangChain 版）。

parse_user_message 使用 LangChain LCEL chain 实现，延迟导入以避免无 langchain 时报错。
preprocess、normalize_validate 等工具函数为本模块内的实际代码。
"""
from .preprocess import preprocess_message, PreprocessResult


def __getattr__(name: str):
    if name == "parse_user_message":
        from src.domain.interaction.chains.nlu_chain import parse_user_message
        return parse_user_message
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["parse_user_message", "preprocess_message", "PreprocessResult"]
