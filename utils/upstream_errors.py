"""上游错误转换工具"""

from typing import Any, Dict

import httpx
from fastapi import HTTPException


def build_upstream_http_exception(
    exc: httpx.HTTPStatusError,
    provider: str,
) -> HTTPException:
    """将 httpx 上游错误转换为 FastAPI HTTPException"""
    detail = _extract_error_detail(exc)
    detail["provider"] = provider
    detail["provider_status_code"] = exc.response.status_code
    return HTTPException(status_code=exc.response.status_code, detail=detail)


def _extract_error_detail(exc: httpx.HTTPStatusError) -> Dict[str, Any]:
    """尽量保留上游 error.message/type/code"""
    try:
        payload = exc.response.json()
    except ValueError:
        return {
            "message": exc.response.text or "Upstream provider error",
            "type": "upstream_error",
        }

    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        return {
            "message": error.get("message", "Upstream provider error"),
            "type": error.get("type", "upstream_error"),
            "code": error.get("code"),
        }

    if isinstance(payload, dict):
        return {
            "message": payload.get("message", "Upstream provider error"),
            "type": payload.get("type", "upstream_error"),
            "code": payload.get("code"),
        }

    return {
        "message": "Upstream provider error",
        "type": "upstream_error",
    }
