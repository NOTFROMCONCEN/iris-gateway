"""Iris AI Gateway - Provider 抽象基类

提供公共的 HTTP 客户端管理、连接池配置和重试机制。
"""

import abc
import asyncio
import logging
from typing import AsyncIterator, Optional, Dict, Any, List

import httpx

from models.schemas import ChatRequest, ChatResponse, StreamChunk

logger = logging.getLogger(__name__)


class BaseProvider(abc.ABC):
    """上游 Provider 抽象基类

    子类只需实现 _build_headers / _build_request_body / _parse_response 等方法，
    公共的 HTTP 客户端管理、重试逻辑由基类统一处理。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 120,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端（带连接池配置）"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=30.0),
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                    keepalive_expiry=300,
                ),
                http2=True,
            )
        return self._client

    async def _retry_request(self, request_fn, operation: str = "request"):
        """带指数退避的重试包装器

        Args:
            request_fn: 异步请求函数
            operation: 操作描述，用于日志
        """
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await request_fn()
            except httpx.HTTPStatusError as e:
                # 4xx 错误不重试（客户端错误）
                if 400 <= e.response.status_code < 500:
                    raise
                last_error = e
                logger.warning(
                    f"{operation} failed (attempt {attempt + 1}/{self.max_retries}): "
                    f"{e.response.status_code}"
                )
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.PoolTimeout) as e:
                last_error = e
                logger.warning(
                    f"{operation} connection error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2 ** attempt)
                logger.info(f"Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)

        # 所有重试耗尽，抛出最后一个错误
        logger.error(f"{operation} failed after {self.max_retries} attempts")
        raise last_error

    @abc.abstractmethod
    async def chat(self, request: ChatRequest, extra_headers: Optional[Dict[str, str]] = None) -> ChatResponse:
        """非流式聊天"""
        ...

    @abc.abstractmethod
    async def chat_stream(self, request: ChatRequest, extra_headers: Optional[Dict[str, str]] = None) -> AsyncIterator[StreamChunk]:
        """流式聊天"""
        ...

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        ...

    async def list_models(self) -> List[Dict[str, Any]]:
        """获取上游可用的模型列表

        默认通过调用上游 /v1/models 端点获取。
        子类可重写以适配不同 API 格式。
        """
        try:
            client = await self._get_client()
            headers = {"Authorization": f"Bearer {self.api_key or ''}"}
            response = await client.get("/v1/models", headers=headers)
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                return [
                    {
                        "id": m.get("id", ""),
                        "display_name": m.get("id", ""),
                        "owned_by": m.get("owned_by", "unknown"),
                    }
                    for m in models if m.get("id")
                ]
        except Exception as e:
            logger.warning(f"Failed to list models from {self.base_url}: {e}")
        return []

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
