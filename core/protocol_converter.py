"""Iris AI Gateway - 协议转换器

负责 OpenAI 格式 ↔ 内部统一格式 ↔ Anthropic 格式的双向转换。
"""

import logging
import time
import uuid
from typing import List, Optional, Dict, Any

from models.schemas import (
    Message, MessageRole, ChatRequest, ChatResponse,
    StreamChunk, ProviderType,
)
from models.openai_schemas import (
    OpenAIChatRequest, OpenAIMessage, OpenAIChatResponse,
    OpenAIChoice, OpenAIUsage, OpenAIStreamChunk, OpenAIModelInfo,
    OpenAIModelListResponse,
)
from models.anthropic_schemas import (
    AnthropicMessageRequest, AnthropicMessage, AnthropicSystemMessage,
    AnthropicMessageResponse, AnthropicContentBlock, AnthropicUsage,
    AnthropicTextContent, AnthropicToolUseContent,
    AnthropicTextDelta, AnthropicModelInfo, AnthropicModelListResponse,
)

logger = logging.getLogger(__name__)


class ProtocolConverter:
    """协议转换器 - 在 OpenAI/Anthropic/内部格式之间转换"""

    # === OpenAI → 内部格式 ===

    @staticmethod
    def openai_to_internal(req: OpenAIChatRequest) -> ChatRequest:
        """将 OpenAI Chat Completions 请求转换为内部 ChatRequest"""
        messages = []
        for msg in req.messages:
            role = ProtocolConverter._map_openai_role(msg.role)
            content = ProtocolConverter._extract_openai_content(msg.content)
            messages.append(Message(
                role=role,
                content=content,
                name=msg.name,
                metadata={"tool_calls": msg.tool_calls, "tool_call_id": msg.tool_call_id}
                if msg.tool_calls or msg.tool_call_id else None,
            ))

        # 推断 provider
        provider = ProtocolConverter._infer_provider_from_model(req.model)

        return ChatRequest(
            messages=messages,
            model=req.model,
            provider=provider,
            temperature=req.temperature,
            max_tokens=req.max_completion_tokens or req.max_tokens,
            top_p=req.top_p,
            stream=req.stream,
            tools=req.tools,
            metadata={
                "source_format": "openai",
                "stop": req.stop,
                "presence_penalty": req.presence_penalty,
                "frequency_penalty": req.frequency_penalty,
                "user": req.user,
                "tool_choice": req.tool_choice,
                "response_format": req.response_format,
                "seed": req.seed,
                "n": req.n,
                "logit_bias": req.logit_bias,
                "max_completion_tokens": req.max_completion_tokens,
            },
        )

    # === Anthropic → 内部格式 ===

    @staticmethod
    def anthropic_to_internal(req: AnthropicMessageRequest) -> ChatRequest:
        """将 Anthropic Messages 请求转换为内部 ChatRequest"""
        messages = []

        # 处理 system 消息
        if req.system:
            system_text = ProtocolConverter._extract_anthropic_system(req.system)
            if system_text:
                messages.append(Message(
                    role=MessageRole.SYSTEM,
                    content=system_text,
                ))

        # 处理 messages
        for msg in req.messages:
            content = ProtocolConverter._extract_anthropic_content(msg.content)
            role = MessageRole.USER if msg.role == "user" else MessageRole.ASSISTANT
            messages.append(Message(role=role, content=content))

        # 推断 provider
        provider = ProtocolConverter._infer_provider_from_model(req.model)

        return ChatRequest(
            messages=messages,
            model=req.model,
            provider=provider,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            top_p=req.top_p,
            stream=req.stream,
            tools=ProtocolConverter._convert_anthropic_tools(req.tools),
            metadata={
                "source_format": "anthropic",
                "stop_sequences": req.stop_sequences,
                "top_k": req.top_k,
                "tool_choice": req.tool_choice,
                "metadata": req.metadata,
            },
        )

    # === 内部格式 → OpenAI 响应 ===

    @staticmethod
    def internal_to_openai_response(resp: ChatResponse) -> OpenAIChatResponse:
        """将内部 ChatResponse 转换为 OpenAI 响应格式"""
        message = OpenAIMessage(
            role="assistant",
            content=resp.message.content,
        )
        choice = OpenAIChoice(
            index=0,
            message=message,
            finish_reason="stop",
        )
        usage = OpenAIUsage(
            prompt_tokens=resp.usage.get("prompt_tokens", 0),
            completion_tokens=resp.usage.get("completion_tokens", 0),
            total_tokens=resp.usage.get("total_tokens", 0),
        )
        return OpenAIChatResponse(
            model=resp.model,
            choices=[choice],
            usage=usage,
        )

    @staticmethod
    def internal_to_openai_stream_chunk(chunk: StreamChunk) -> OpenAIStreamChunk:
        """将内部 StreamChunk 转换为 OpenAI 流式块"""
        delta = {}
        if chunk.delta:
            delta["content"] = chunk.delta
        elif not chunk.finish_reason:
            delta["content"] = chunk.delta or ""

        choice = OpenAIChoice(
            index=0,
            delta=delta if chunk.delta or chunk.finish_reason else {},
            finish_reason=chunk.finish_reason,
        )
        return OpenAIStreamChunk(
            id=chunk.id,
            model=chunk.model,
            choices=[choice],
        )

    # === 内部格式 → Anthropic 响应 ===

    @staticmethod
    def internal_to_anthropic_response(resp: ChatResponse) -> AnthropicMessageResponse:
        """将内部 ChatResponse 转换为 Anthropic 响应格式"""
        content_block = AnthropicContentBlock(
            type="text",
            text=resp.message.content,
        )
        usage = AnthropicUsage(
            input_tokens=resp.usage.get("prompt_tokens", 0),
            output_tokens=resp.usage.get("completion_tokens", 0),
        )
        return AnthropicMessageResponse(
            id=resp.id,
            model=resp.model,
            content=[content_block],
            stop_reason="end_turn",
            usage=usage,
        )

    @staticmethod
    def internal_to_anthropic_stream_events(chunk: StreamChunk) -> List[Dict[str, Any]]:
        """将内部 StreamChunk 转换为 Anthropic 流式事件列表"""
        events = []

        if chunk.delta:
            events.append({
                "event": "content_block_delta",
                "data": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {
                        "type": "text_delta",
                        "text": chunk.delta,
                    }
                }
            })

        if chunk.finish_reason:
            output_tokens = 0
            if chunk.usage:
                output_tokens = chunk.usage.get("output_tokens", 0)

            # content_block_stop
            events.append({
                "event": "content_block_stop",
                "data": {
                    "type": "content_block_stop",
                    "index": 0,
                }
            })
            # message_delta
            events.append({
                "event": "message_delta",
                "data": {
                    "type": "message_delta",
                    "delta": {
                        "stop_reason": ProtocolConverter._map_finish_reason_to_anthropic(
                            chunk.finish_reason
                        ),
                        "stop_sequence": None,
                    },
                    "usage": {
                        "output_tokens": output_tokens,
                    }
                }
            })
            # message_stop
            events.append({
                "event": "message_stop",
                "data": {
                    "type": "message_stop",
                }
            })

        return events

    # === Anthropic 流式事件构建 ===

    @staticmethod
    def build_anthropic_message_start(model: str, message_id: str) -> Dict[str, Any]:
        """构建 Anthropic message_start 事件"""
        return {
            "event": "message_start",
            "data": {
                "type": "message_start",
                "message": {
                    "id": message_id,
                    "type": "message",
                    "role": "assistant",
                    "model": model,
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                    }
                }
            }
        }

    @staticmethod
    def build_anthropic_content_block_start() -> Dict[str, Any]:
        """构建 Anthropic content_block_start 事件"""
        return {
            "event": "content_block_start",
            "data": {
                "type": "content_block_start",
                "index": 0,
                "content_block": {
                    "type": "text",
                    "text": "",
                }
            }
        }

    @staticmethod
    def build_anthropic_ping() -> Dict[str, Any]:
        """构建 Anthropic ping 事件"""
        return {
            "event": "ping",
            "data": {
                "type": "ping",
            }
        }

    # === 模型列表转换 ===

    @staticmethod
    def build_openai_model_list(models: List[Dict[str, str]]) -> OpenAIModelListResponse:
        """构建 OpenAI 模型列表响应"""
        model_infos = [
            OpenAIModelInfo(id=m["id"], owned_by=m.get("owned_by", "iris-gateway"))
            for m in models
        ]
        return OpenAIModelListResponse(data=model_infos)

    @staticmethod
    def build_anthropic_model_list(models: List[Dict[str, str]]) -> AnthropicModelListResponse:
        """构建 Anthropic 模型列表响应"""
        model_infos = [
            AnthropicModelInfo(id=m["id"], display_name=m.get("display_name", m["id"]))
            for m in models
        ]
        return AnthropicModelListResponse(data=model_infos)

    # === 内部工具方法 ===

    @staticmethod
    def _map_openai_role(role: str) -> MessageRole:
        """映射 OpenAI role 到内部 MessageRole"""
        mapping = {
            "system": MessageRole.SYSTEM,
            "user": MessageRole.USER,
            "assistant": MessageRole.ASSISTANT,
            "tool": MessageRole.TOOL,
        }
        return mapping.get(role, MessageRole.USER)

    @staticmethod
    def _extract_openai_content(content) -> str:
        """提取 OpenAI 消息内容为字符串"""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            # 多模态内容，提取文本部分
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif isinstance(block, str):
                    texts.append(block)
            return "\n".join(texts)
        return str(content)

    @staticmethod
    def _extract_anthropic_system(system) -> str:
        """提取 Anthropic system 消息为字符串"""
        if isinstance(system, str):
            return system
        if isinstance(system, list):
            texts = []
            for block in system:
                if isinstance(block, AnthropicSystemMessage):
                    texts.append(block.text)
                elif isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
            return "\n".join(texts)
        return ""

    @staticmethod
    def _extract_anthropic_content(content) -> str:
        """提取 Anthropic 消息内容为字符串"""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, AnthropicTextContent):
                    texts.append(block.text)
                elif isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif isinstance(block, str):
                    texts.append(block)
            return "\n".join(texts)
        return str(content)

    @staticmethod
    def _convert_anthropic_tools(tools: Optional[List]) -> Optional[List[Dict[str, Any]]]:
        """转换 Anthropic 工具定义为内部格式"""
        if not tools:
            return None
        result = []
        for tool in tools:
            if hasattr(tool, "model_dump"):
                tool_dict = tool.model_dump()
            elif isinstance(tool, dict):
                tool_dict = tool
            else:
                continue
            result.append({
                "type": "function",
                "function": {
                    "name": tool_dict.get("name", ""),
                    "description": tool_dict.get("description", ""),
                    "parameters": tool_dict.get("input_schema", {}),
                }
            })
        return result

    @staticmethod
    def _infer_provider_from_model(model: str) -> ProviderType:
        """根据模型名称推断 Provider"""
        model_lower = model.lower()
        if any(kw in model_lower for kw in ["claude", "anthropic"]):
            return ProviderType.ANTHROPIC
        return ProviderType.OPENAI

    @staticmethod
    def _map_finish_reason_to_anthropic(reason: str) -> str:
        """映射 finish_reason 到 Anthropic 格式"""
        mapping = {
            "stop": "end_turn",
            "length": "max_tokens",
            "tool_calls": "tool_use",
            "content_filter": "end_turn",
        }
        return mapping.get(reason, "end_turn")
