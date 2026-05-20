"""Iris AI Gateway - OpenAI Provider 测试"""

from models.schemas import ChatRequest, Message, MessageRole, ProviderType
from providers.openai_provider import OpenAIProvider


def test_openai_provider_uses_max_completion_tokens_when_present():
    provider = OpenAIProvider(api_key="test-key")
    request = ChatRequest(
        model="gpt-4o",
        provider=ProviderType.OPENAI,
        messages=[Message(role=MessageRole.USER, content="Hello!")],
        max_tokens=256,
        metadata={
            "max_completion_tokens": 256,
            "logit_bias": {"42": -10},
        },
    )

    body = provider._build_request_body(request)

    assert body["max_completion_tokens"] == 256
    assert "max_tokens" not in body
    assert body["logit_bias"] == {"42": -10}
