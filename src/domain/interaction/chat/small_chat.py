"""
LangChain 版小聊天入口：替换原 interaction.chat.small_chat。
外部代码 import small_chat_reply 即可无缝切换。
"""
from src.domain.interaction.chains.small_chat_chain import small_chat_reply

__all__ = ["small_chat_reply"]
