"""DEEPSEEK 配置"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DeepSeekConfig(BaseSettings):
    api_key: str = Field(
        default="", description="DeepSeek API Key（环境变量 DEEP_SEEK_API_KEY）"
    )
    model: str = Field(default="deepseek-chat", description="模型，如V3, R1")
    base_url: str = Field(
        default="https://api.deepseek.com", description="base_url链接"
    )

    model_config = SettingsConfigDict(
        env_prefix="DEEP_SEEK_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


__all__ = ["DeepSeekConfig"]
