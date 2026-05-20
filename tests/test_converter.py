"""Iris AI Gateway - 协议转换器测试"""

import pytest
from models.schemas import Message, MessageRole, ChatRequest, ProviderType
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
