from pathlib import Path
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config.api import OpenAIConfig
from src.config.api import DeepSeekConfig
from src.config.api import WechatSpiderConfig
from src.config.database import BetterMeMySQLConfig

# NLU 解析可选的 LLM 供应商
LLMProviderType = Literal["deepseek", "openai"]


def _default_soul_path() -> Optional[Path]:
    """默认 soul 文件路径：项目根下 src/soul/rude.md（供小聊天人格注入）。"""
    try:
        root = Path(__file__).resolve().parent.parent.parent
        return root / "src" / "soul" / "rude.md"
    except Exception:
        return None


class Config(BaseSettings):
    """应用全局配置"""

    # ============ 应用基础配置 ============
    app_name: str = Field(default="BetterMe", description="应用名称")
    soul_file_path: Optional[Path] = Field(
        default_factory=_default_soul_path,
        description="小聊天人格设定文件路径（如 rude.md），不设则自动探测 src/soul/rude.md",
    )
    environment: str = Field(
        default="development", description="运行环境: development/pre/production"
    )
    debug: bool = Field(default=False, description="调试模式")

    # ============ 数据库配置 ============
    better_me: BetterMeMySQLConfig = Field(default_factory=BetterMeMySQLConfig)

    # ============ Auth / JWT 配置 ============
    JWT_SECRET: str = Field(
        default="change-me-in-prod",
        description="JWT 签名密钥，生产环境必须通过环境变量 JWT_SECRET 覆盖",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT 签名算法",
    )
    JWT_EXPIRE_SECONDS: int = Field(
        default=7 * 24 * 3600,
        description="JWT 过期时间（秒），默认 7 天",
    )

    # ============ LLM（交互层 NLU）：供应商 + 各供应商配置 ============
    llm_provider: LLMProviderType = Field(
        default="deepseek",
        description="NLU 使用的 LLM 供应商: deepseek | openai",
    )
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    deepseek: DeepSeekConfig = Field(default_factory=DeepSeekConfig)

    #
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


__all__ = ["Config", "LLMProviderType"]
