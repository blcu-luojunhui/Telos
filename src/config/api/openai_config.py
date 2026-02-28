"""OpenAI 配置，用于 NLU 解析等。"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenAIConfig(BaseSettings):
    api_key: str = Field(default="", description="OpenAI API Key")
    model: str = Field(default="gpt-4o", description="模型，如 gpt-4o / gpt-4o-mini")

    model_config = SettingsConfigDict(
        env_prefix="OPENAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


__all__ = ["OpenAIConfig"]
