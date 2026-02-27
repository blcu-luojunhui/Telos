from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config.api import OpenAIConfig
from src.config.api import DeepSeekConfig
from src.config.database import BetterMeMySQLConfig


class Config(BaseSettings):
    """应用全局配置"""

    # ============ 应用基础配置 ============
    app_name: str = Field(default="BetterMe", description="应用名称")
    environment: str = Field(
        default="development", description="运行环境: development/pre/production"
    )
    debug: bool = Field(default=False, description="调试模式")

    # ============ 数据库配置 ============
    better_me: BetterMeMySQLConfig = Field(default_factory=BetterMeMySQLConfig)

    # ============ LLM / OpenAI（交互层 NLU 等） ============
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    deepseek: DeepSeekConfig = Field(default_factory=DeepSeekConfig)

    #
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


__all__ = ["Config"]
