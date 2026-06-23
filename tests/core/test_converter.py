"""Iris AI Gateway - 协议转换器测试"""

import pytest
from models.schemas import Message, MessageRole, ChatRequest, ChatResponse, ProviderType, StreamChunk
from models.openai_schemas import OpenAIChatRequest, OpenAIMessage
from models.anthropic_schemas import (
    AnthropicMessageRequest,
    AnthropicMessage,
    AnthropicTextContent,
    AnthropicToolResultContent,
    AnthropicToolUseContent,
)
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

    def test_openai_to_internal_preserves_advanced_parameters(self):
        """测试 OpenAI 高级参数进入内部 metadata"""
        req = OpenAIChatRequest(
            model="gpt-4o",
            messages=[OpenAIMessage(role="user", content="Hello!")],
            max_completion_tokens=256,
            logit_bias={"42": -10},
        )

        internal = ProtocolConverter.openai_to_internal(req)

        assert internal.max_tokens == 256
        assert internal.metadata["max_completion_tokens"] == 256
        assert internal.metadata["logit_bias"] == {"42": -10}

    def test_openai_to_internal_preserves_gateway_session_fields(self):
        """测试 OpenAI 兼容请求可显式携带跨端会话字段"""
        req = OpenAIChatRequest(
            model="gpt-4o",
            messages=[OpenAIMessage(role="user", content="Hello!")],
            session_id="sess-shared",
            persona_id="coder",
        )

        internal = ProtocolConverter.openai_to_internal(req)

        assert internal.session_id == "sess-shared"
        assert internal.persona_id == "coder"

    def test_openai_to_internal_preserves_multimodal_content_blocks(self):
        """测试 OpenAI 多模态内容块不会被静默丢弃"""
        content = [
            {"type": "text", "text": "Describe this image."},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
        ]
        req = OpenAIChatRequest(
            model="gpt-4o",
            messages=[OpenAIMessage(role="user", content=content)],
        )

        internal = ProtocolConverter.openai_to_internal(req)

        assert internal.messages[0].content == "Describe this image."
        assert internal.messages[0].metadata["openai_content"] == content

    def test_anthropic_to_internal_preserves_image_blocks(self):
        """测试 Anthropic 图片内容块进入内部 metadata"""
        image_block = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": "abc",
            },
        }
        req = AnthropicMessageRequest(
            model="claude-sonnet-4-20250514",
            messages=[
                AnthropicMessage(
                    role="user",
                    content=[
                        AnthropicTextContent(text="Describe this image."),
                        image_block,
                    ],
                ),
            ],
            max_tokens=100,
        )

        internal = ProtocolConverter.anthropic_to_internal(req)

        assert internal.messages[0].content == "Describe this image."
        assert internal.messages[0].metadata["anthropic_content"][1] == image_block

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

    def test_anthropic_to_internal_reads_session_from_metadata(self):
        """测试 Anthropic 客户端可通过 metadata 恢复共享会话"""
        req = AnthropicMessageRequest(
            model="claude-sonnet-4-20250514",
            messages=[AnthropicMessage(role="user", content="Hello Claude!")],
            metadata={"session_id": "sess-shared", "persona_id": "coder"},
            max_tokens=100,
        )

        internal = ProtocolConverter.anthropic_to_internal(req)

        assert internal.session_id == "sess-shared"
        assert internal.persona_id == "coder"

    def test_anthropic_to_internal_preserves_tool_blocks(self):
        """测试 Anthropic 工具内容块进入内部 metadata"""
        req = AnthropicMessageRequest(
            model="claude-sonnet-4-20250514",
            messages=[
                AnthropicMessage(
                    role="assistant",
                    content=[
                        AnthropicTextContent(text="I will look it up."),
                        AnthropicToolUseContent(
                            id="toolu_1",
                            name="lookup",
                            input={"q": "iris"},
                        ),
                    ],
                ),
                AnthropicMessage(
                    role="user",
                    content=[
                        AnthropicToolResultContent(
                            tool_use_id="toolu_1",
                            content="result",
                        ),
                    ],
                ),
            ],
            max_tokens=100,
        )

        internal = ProtocolConverter.anthropic_to_internal(req)

        assert internal.messages[0].metadata["anthropic_content"][1]["type"] == "tool_use"
        assert internal.messages[1].metadata["anthropic_content"][0]["type"] == "tool_result"

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

    def test_internal_to_openai_response_preserves_tool_calls(self):
        """测试内部响应中的工具调用能输出为 OpenAI tool_calls"""
        tool_calls = [{
            "id": "call_1",
            "type": "function",
            "function": {"name": "lookup", "arguments": "{\"q\":\"iris\"}"},
        }]
        response = ChatResponse(
            message=Message(
                role=MessageRole.ASSISTANT,
                content="",
                metadata={
                    "tool_calls": tool_calls,
                    "finish_reason": "tool_calls",
                },
            ),
            provider=ProviderType.OPENAI,
            model="gpt-4o",
            persona_id="default",
            session_id="session-1",
        )

        result = ProtocolConverter.internal_to_openai_response(response)

        assert result.choices[0].message.tool_calls == tool_calls
        assert result.choices[0].message.content is None
        assert result.choices[0].finish_reason == "tool_calls"

    def test_internal_to_anthropic_response_preserves_tool_use_content(self):
        """测试内部响应中的 Anthropic tool_use 内容块能输出"""
        response = ChatResponse(
            message=Message(
                role=MessageRole.ASSISTANT,
                content="",
                metadata={
                    "anthropic_content": [{
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "lookup",
                        "input": {"q": "iris"},
                    }],
                    "stop_reason": "tool_use",
                },
            ),
            provider=ProviderType.ANTHROPIC,
            model="claude-sonnet-4",
            persona_id="default",
            session_id="session-1",
        )

        result = ProtocolConverter.internal_to_anthropic_response(response)

        assert result.content[0].type == "tool_use"
        assert result.content[0].name == "lookup"
        assert result.stop_reason == "tool_use"
