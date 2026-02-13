from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .mysql import BetterMeMySQLConfig


class Config(BaseSettings):
    """应用全局配置"""

    # ============ 应用基础配置 ============
    app_name: str = Field(default="BetterMe", description="应用名称")
    environment: str = Field(
        default="development", description="运行环境: development/pre/production"
    )
    debug: bool = Field(default=False, description="调试模式")

    # ============ 数据库配置 ============
    mysql_config: BetterMeMySQLConfig = Field(default_factory=BetterMeMySQLConfig)

    #
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


__all__ = ["Config"]
