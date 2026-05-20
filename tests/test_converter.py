"""Iris AI Gateway - 协议转换器测试"""

import pytest
from models.schemas import Message, MessageRole, ChatRequest, ProviderType, StreamChunk
from models.openai_schemas import OpenAIChatRequest, OpenAIMessage
from models.anthropic_schemas import AnthropicMessageRequest, AnthropicMessage
from core.protocol_converter import ProtocolConverter


class TestProtocolConverter:
    """测试协议转换器"""

    def test_openai_to_internal(self):
        """测试 OpenAI 到内部格式转换"""
        req = OpenAIChatRequest(
            model="gpt-4o",
            messages=[
                OpenAIMessage(role="system", content="You are a helpful assistant."),
                OpenAIMessage(role="user", content="Hello!"),
            ],
            temperature=0.7,
            max_tokens=100,
        )
        internal = ProtocolConverter.openai_to_internal(req)

        assert internal.model == "gpt-4o"
        assert len(internal.messages) == 2
        assert internal.messages[0].role == MessageRole.SYSTEM
        assert internal.messages[1].role == MessageRole.USER
        assert internal.messages[1].content == "Hello!"
        assert internal.temperature == 0.7
        assert internal.provider == ProviderType.OPENAI

    def test_anthropic_to_internal(self):
        """测试 Anthropic 到内部格式转换"""
        req = AnthropicMessageRequest(
            model="claude-sonnet-4-20250514",
            messages=[
                AnthropicMessage(role="user", content="Hello Claude!"),
            ],
            system="You are Claude.",
            max_tokens=100,
        )
        internal = ProtocolConverter.anthropic_to_internal(req)

        assert internal.model == "claude-sonnet-4-20250514"
        assert len(internal.messages) == 2  # system + user
        assert internal.messages[0].role == MessageRole.SYSTEM
        assert internal.messages[1].role == MessageRole.USER
        assert internal.provider == ProviderType.ANTHROPIC

    def test_infer_provider_from_model(self):
        """测试模型名称推断 Provider"""
        assert ProtocolConverter._infer_provider_from_model("gpt-4o") == ProviderType.OPENAI
        assert ProtocolConverter._infer_provider_from_model("claude-sonnet-4") == ProviderType.ANTHROPIC
        assert ProtocolConverter._infer_provider_from_model("anthropic-claude") == ProviderType.ANTHROPIC

    def test_openai_stream_finish_reason_is_not_in_delta(self):
        """测试 OpenAI 流式结束原因位于 choice.finish_reason"""
        chunk = StreamChunk(
            id="chunk-1",
            delta="",
            provider=ProviderType.OPENAI,
            model="gpt-4o",
            finish_reason="stop",
        )

        result = ProtocolConverter.internal_to_openai_stream_chunk(chunk)

        assert result.choices[0].delta == {}
        assert result.choices[0].finish_reason == "stop"

    def test_anthropic_stream_finish_event_uses_chunk_usage(self):
        """测试 Anthropic 流式结束事件携带上游 output_tokens"""
        chunk = StreamChunk(
            id="chunk-1",
            delta="",
            provider=ProviderType.ANTHROPIC,
            model="claude-sonnet-4",
            finish_reason="end_turn",
            usage={"output_tokens": 12},
        )

        events = ProtocolConverter.internal_to_anthropic_stream_events(chunk)
        message_delta = next(e for e in events if e["event"] == "message_delta")

        assert message_delta["data"]["usage"]["output_tokens"] == 12
        assert events[-1]["event"] == "message_stop"
