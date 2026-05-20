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


def test_openai_provider_parses_tool_calls_from_response():
    provider = OpenAIProvider(api_key="test-key")
    request = ChatRequest(
        model="gpt-4o",
        provider=ProviderType.OPENAI,
        messages=[Message(role=MessageRole.USER, content="Use a tool")],
    )
    tool_calls = [{
        "id": "call_1",
        "type": "function",
        "function": {"name": "lookup", "arguments": "{\"q\":\"iris\"}"},
    }]

    response = provider._parse_response(
        {
            "id": "chatcmpl-test",
            "model": "gpt-4o",
            "choices": [{
                "message": {"role": "assistant", "content": None, "tool_calls": tool_calls},
                "finish_reason": "tool_calls",
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        },
        request,
    )

    assert response.message.content == ""
    assert response.message.metadata["tool_calls"] == tool_calls
    assert response.message.metadata["finish_reason"] == "tool_calls"


def test_openai_provider_builds_request_with_preserved_multimodal_content():
    provider = OpenAIProvider(api_key="test-key")
    content = [
        {"type": "text", "text": "Describe this image."},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
    ]
    request = ChatRequest(
        model="gpt-4o",
        provider=ProviderType.OPENAI,
        messages=[
            Message(
                role=MessageRole.USER,
                content="Describe this image.",
                metadata={"openai_content": content},
            )
        ],
    )

    body = provider._build_request_body(request)

    assert body["messages"][0]["content"] == content
