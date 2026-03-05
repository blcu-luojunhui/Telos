import aiohttp
from typing import Optional, Union, Dict, Any


class AsyncHttpClient:
    def __init__(
        self,
        timeout: int = 10,
        max_connections: int = 100,
        default_headers: Optional[Dict[str, str]] = None,
    ):
        """
        简化版异步 HTTP 客户端

        :param timeout: 请求超时时间（秒）
        :param max_connections: 连接池最大连接数
        :param default_headers: 默认请求头
        """
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.connector = aiohttp.TCPConnector(limit=max_connections)
        self.default_headers = default_headers or {}
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            connector=self.connector, timeout=self.timeout, headers=self.default_headers
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    async def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Union[Dict[str, Any], str]:
        """核心请求方法"""
        request_headers = {**self.default_headers, **(headers or {})}

        try:
            async with self.session.request(
                method,
                url,
                params=params,
                data=data,
                json=json,
                headers=request_headers,
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "")

                if "application/json" in content_type:
                    return await response.json()
                return await response.text()

        except aiohttp.ClientResponseError as e:
            print(f"HTTP error: {e.status} {e.message}")
            raise
        except aiohttp.ClientError as e:
            print(f"Network error: {str(e)}")
            raise

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Union[Dict[str, Any], str]:
        """GET 请求"""
        return await self.request("GET", url, params=params, headers=headers)

    async def post(
        self,
        url: str,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Union[Dict[str, Any], str]:
        """POST 请求"""
        return await self.request("POST", url, data=data, json=json, headers=headers)

    async def put(
        self,
        url: str,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Union[Dict[str, Any], str]:
        """
        PUT 请求

        通常用于更新资源，可以发送表单数据或 JSON 数据
        """
        return await self.request("PUT", url, data=data, json=json, headers=headers)
