"""Iris AI Gateway - 上游错误转换测试"""

import httpx

from utils.upstream_errors import build_upstream_http_exception


def _status_error(status_code: int, body) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(status_code, json=body, request=request)
    return httpx.HTTPStatusError("upstream failed", request=request, response=response)


def test_build_upstream_http_exception_preserves_error_shape():
    exc = _status_error(
        429,
        {
            "error": {
                "message": "rate limited",
                "type": "rate_limit_error",
                "code": "rate_limit_exceeded",
            }
        },
    )

    result = build_upstream_http_exception(exc, "openai")

    assert result.status_code == 429
    assert result.detail == {
        "message": "rate limited",
        "type": "rate_limit_error",
        "code": "rate_limit_exceeded",
        "provider": "openai",
        "provider_status_code": 429,
    }


def test_build_upstream_http_exception_handles_non_error_payload():
    exc = _status_error(400, {"message": "bad request", "type": "invalid_request"})

    result = build_upstream_http_exception(exc, "anthropic")

    assert result.status_code == 400
    assert result.detail["message"] == "bad request"
    assert result.detail["type"] == "invalid_request"
    assert result.detail["provider"] == "anthropic"
