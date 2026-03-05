from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from src.config.api import WechatSpiderConfig
from src.infra.shared import AsyncHttpClient


logger = logging.getLogger(__name__)


# 微信搜索
async def wechat_search(keyword: str, page: str = "1") -> Optional[Dict[str, Any]]:
    """
    微信搜索核心方法。

    约定：
    - 入参：
        - keyword: 搜索关键词
        - page:    页码，字符串形式（默认 "1"）
    - 返回：
        - dict:    搜索结果（结构由你后续接入真实接口时自行定义）
        - None:    表示调用失败

    当前为占位实现，只做日志记录并返回模拟数据。
    接入真实接口时，你只需要把下面「模拟返回」部分替换为实际 HTTP 请求。
    """
    kw = (keyword or "").strip()
    pg = (page or "1").strip() or "1"

    if not kw:
        logger.warning("weixin_search 调用时未提供关键词")
        return None

    logger.info("weixin_search 被调用：keyword=%s, page=%s", kw, pg)

    base_url = (WechatSpiderConfig().base_url or "").rstrip("/")
    if not base_url:
        logger.error("WechatSpiderConfig.base_url 未配置（环境变量 WECHAT_SPIDER_BASE_URL）")
        return None
    url = "{}/keyword".format(base_url)
    headers = {"Content-Type": "application/json"}
    payload = json.dumps({"keyword": keyword, "cursor": page})
    try:
        async with AsyncHttpClient(timeout=120) as http_client:
            response = await http_client.post(url=url, headers=headers, data=payload)

    except Exception as e:
        return None

    return response
