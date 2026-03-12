"""Weixin 爬虫配置"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WechatSpiderConfig(BaseSettings):
    base_url: str = Field(
        default="", description="base_url链接"
    )

    model_config = SettingsConfigDict(
        env_prefix="WECHAT_SPIDER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


__all__ = ["WechatSpiderConfig"]
