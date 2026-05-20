"""Iris AI Gateway - 统一异常定义

提供自定义异常层次结构，避免暴露内部错误细节给客户端。
"""

from typing import Optional


class IrisGatewayError(Exception):
    """Iris 网关基础异常"""

    def __init__(self, message: str, code: str = "internal_error", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class ProviderNotConfiguredError(IrisGatewayError):
    """Provider 未配置"""

    def __init__(self, provider: str):
        super().__init__(
            message=f"Provider '{provider}' is not configured. Please set the corresponding API key.",
            code="provider_not_configured",
            status_code=502,
        )


class ProviderUpstreamError(IrisGatewayError):
    """上游 Provider 请求失败"""

    def __init__(self, provider: str, detail: str, status_code: int = 502):
        # 脱敏：不暴露上游原始错误细节
        super().__init__(
            message=f"Upstream provider '{provider}' returned an error. Please try again later.",
            code="upstream_error",
            status_code=status_code,
        )
        self._internal_detail = detail

    @property
    def internal_detail(self) -> str:
        """内部错误详情（仅用于日志，不返回给客户端）"""
        return self._internal_detail


class ProviderTimeoutError(IrisGatewayError):
    """上游 Provider 超时"""

    def __init__(self, provider: str, timeout: int):
        super().__init__(
            message=f"Request to '{provider}' timed out after {timeout}s.",
            code="upstream_timeout",
            status_code=504,
        )


class AuthenticationError(IrisGatewayError):
    """认证失败"""

    def __init__(self, detail: str = "Invalid or missing API Key"):
        super().__init__(
            message=detail,
            code="authentication_error",
            status_code=401,
        )


class PersonaNotFoundError(IrisGatewayError):
    """人格配置未找到"""

    def __init__(self, persona_id: str):
        super().__init__(
            message=f"Persona '{persona_id}' not found, using default.",
            code="persona_not_found",
            status_code=200,  # 降级处理，不是致命错误
        )
