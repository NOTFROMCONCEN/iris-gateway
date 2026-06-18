"""Iris AI Gateway - API Key 认证中间件

支持 Bearer Token、x-api-key、api-key 多种认证方式。
路径白名单支持精确匹配和前缀匹配。
"""

import logging
from typing import Optional, List, Set

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """API Key 认证中间件"""

    def __init__(self, app, api_keys: Optional[List[str]] = None):
        super().__init__(app)
        self.api_keys: Set[str] = set(api_keys or [])
        # 精确匹配的公开路径
        self.public_paths: Set[str] = {
            "/health",
            "/ready",
            "/",
            "/docs",
            "/openapi.json",
            "/redoc",
        }
        # 前缀匹配的公开路径（静态资源等）
        self.public_prefixes: tuple = ("/docs/", "/redoc/", "/static/")

    def _is_public_path(self, path: str) -> bool:
        """检查路径是否为公开路由"""
        if path in self.public_paths:
            return True
        return any(path.startswith(prefix) for prefix in self.public_prefixes)

    def _extract_api_key(self, request: Request) -> Optional[str]:
        """从请求中提取 API Key"""
        # 从 Authorization header 提取
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()

        # 从 x-api-key header 提取（Anthropic 风格）
        api_key = request.headers.get("x-api-key", "")
        if api_key:
            return api_key

        # 从 api-key header 提取
        api_key = request.headers.get("api-key", "")
        if api_key:
            return api_key

        return None

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        path = request.url.path

        # 公开路由直接放行
        if self._is_public_path(path):
            return await call_next(request)

        # 如果没有配置 API Key，则放行所有请求
        if not self.api_keys:
            return await call_next(request)

        # 提取并验证 API Key
        api_key = self._extract_api_key(request)
        if not api_key:
            logger.warning(f"Missing API Key for {request.method} {path}")
            raise HTTPException(status_code=401, detail="Missing API Key")

        if api_key not in self.api_keys:
            logger.warning(f"Invalid API Key for {request.method} {path}")
            raise HTTPException(status_code=401, detail="Invalid API Key")

        # 将 API Key 附加到请求状态
        request.state.api_key = api_key
        return await call_next(request)
