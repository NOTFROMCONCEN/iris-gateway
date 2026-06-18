"""Iris AI Gateway - Anthropic Provider 测试"""

from models.schemas import ChatRequest, Message, MessageRole, ProviderType
from providers.anthropic_provider import AnthropicProvider


def test_anthropic_provider_builds_request_with_preserved_tool_result():
    provider = AnthropicProvider(api_key="test-key")
    tool_result = [{
        "type": "tool_result",
        "tool_use_id": "toolu_1",
        "content": "result",
    }]
    request = ChatRequest(
        model="claude-sonnet-4",
        provider=ProviderType.ANTHROPIC,
        messages=[
            Message(
                role=MessageRole.USER,
                content="result",
                metadata={"anthropic_content": tool_result},
            )
        ],
    )

    body = provider._build_request_body(request)

    assert body["messages"][0]["content"] == tool_result


def test_anthropic_provider_parses_tool_use_response():
    provider = AnthropicProvider(api_key="test-key")
    request = ChatRequest(
        model="claude-sonnet-4",
        provider=ProviderType.ANTHROPIC,
        messages=[Message(role=MessageRole.USER, content="Use a tool")],
    )
    tool_use = {
        "type": "tool_use",
        "id": "toolu_1",
        "name": "lookup",
        "input": {"q": "iris"},
    }

    response = provider._parse_response(
        {
            "id": "msg_test",
            "model": "claude-sonnet-4",
            "content": [tool_use],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 5, "output_tokens": 3},
        },
        request,
    )

    assert response.message.metadata["anthropic_content"] == [tool_use]
    assert response.message.metadata["stop_reason"] == "tool_use"
