"""Iris AI Gateway - Anthropic 上游 Provider

负责调用 Anthropic Messages API，支持伪装为 Claude Code。
继承 BaseProvider 的连接池和重试机制。
"""

import logging
import json
import uuid
from typing import AsyncIterator, Optional, Dict, Any, List

import httpx

from providers.base import BaseProvider
from models.schemas import (
    ChatRequest, ChatResponse, StreamChunk,
    Message, MessageRole, ProviderType,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic 上游 Provider"""

    DEFAULT_BASE_URL = "https://api.anthropic.com"
    API_VERSION = "2023-06-01"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 120,
        auth_header: str = "x-api-key",  # 支持自定义认证 header (如 moonshot 用 api-key)
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url or self.DEFAULT_BASE_URL,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
        self.auth_header = auth_header

    def _build_headers(self, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": self.API_VERSION,
            self.auth_header: self.api_key or "",
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _build_request_body(self, request: ChatRequest) -> Dict[str, Any]:
        """将内部 ChatRequest 转换为 Anthropic API 请求体"""
        system_text = ""
        messages = []

        for msg in request.messages:
            if msg.role == MessageRole.SYSTEM:
                system_text += msg.content + "\n"
            elif msg.role in (MessageRole.USER, MessageRole.ASSISTANT):
                messages.append({
                    "role": "user" if msg.role == MessageRole.USER else "assistant",
                    "content": msg.content,
                })
            elif msg.role == MessageRole.TOOL:
                # 工具结果作为 user 消息
                messages.append({
                    "role": "user",
                    "content": msg.content,
                })

        body: Dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
        }

        if system_text.strip():
            body["system"] = system_text.strip()

        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.top_p is not None:
            body["top_p"] = request.top_p

        # 处理 stop_sequences
        stop = request.metadata.get("stop_sequences") or request.metadata.get("stop")
        if stop:
            if isinstance(stop, str):
                body["stop_sequences"] = [stop]
            elif isinstance(stop, list):
                body["stop_sequences"] = stop

        # 处理 tools
        if request.tools:
            anthropic_tools = []
            for tool in request.tools:
                if isinstance(tool, dict):
                    func = tool.get("function", tool)
                    anthropic_tools.append({
                        "name": func.get("name", ""),
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {}),
                    })
            if anthropic_tools:
                body["tools"] = anthropic_tools

        return body

    async def chat(self, request: ChatRequest, extra_headers: Optional[Dict[str, str]] = None) -> ChatResponse:
        """非流式调用 Anthropic API（带重试）"""
        client = await self._get_client()
        headers = self._build_headers(extra_headers)
        body = self._build_request_body(request)

        async def _do_request():
            response = await client.post("/v1/messages", headers=headers, json=body)
            response.raise_for_status()
            return self._parse_response(response.json(), request)

        try:
            return await self._retry_request(_do_request, "Anthropic chat")
        except httpx.HTTPStatusError as e:
            logger.error(f"Anthropic API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Anthropic request failed: {e}")
            raise

    async def chat_stream(self, request: ChatRequest, extra_headers: Optional[Dict[str, str]] = None) -> AsyncIterator[StreamChunk]:
        """流式调用 Anthropic API"""
        client = await self._get_client()
        headers = self._build_headers(extra_headers)
        body = self._build_request_body(request)
        body["stream"] = True

        msg_id = f"iris-{uuid.uuid4().hex[:12]}"

        try:
            async with client.stream("POST", "/v1/messages", headers=headers, json=body) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            async for chunk in self._parse_stream_event(data, msg_id, request.model):
                                yield chunk
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse SSE data: {data_str}")
                            continue

        except httpx.HTTPStatusError as e:
            logger.error(f"Anthropic stream error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Anthropic stream failed: {e}")
            raise

    def _parse_response(self, data: Dict[str, Any], request: ChatRequest) -> ChatResponse:
        """解析 Anthropic 响应为内部格式"""
        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        usage_data = data.get("usage", {})
        return ChatResponse(
            id=data.get("id", f"iris-{uuid.uuid4().hex[:12]}"),
            message=Message(role=MessageRole.ASSISTANT, content=content),
            provider=ProviderType.ANTHROPIC,
            model=data.get("model", request.model),
            persona_id=request.persona_id or "default",
            session_id=request.session_id or "",
            usage={
                "prompt_tokens": usage_data.get("input_tokens", 0),
                "completion_tokens": usage_data.get("output_tokens", 0),
                "total_tokens": usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
            },
        )

    async def _parse_stream_event(self, event: Dict[str, Any], msg_id: str, model: str) -> AsyncIterator[StreamChunk]:
        """解析 Anthropic SSE 事件为内部 StreamChunk"""
        event_type = event.get("type", "")

        if event_type == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                yield StreamChunk(
                    id=msg_id,
                    delta=delta.get("text", ""),
                    provider=ProviderType.ANTHROPIC,
                    model=model,
                )

        elif event_type == "message_delta":
            delta = event.get("delta", {})
            stop_reason = delta.get("stop_reason")
            if stop_reason:
                yield StreamChunk(
                    id=msg_id,
                    delta="",
                    provider=ProviderType.ANTHROPIC,
                    model=model,
                    finish_reason=stop_reason,
                )

    async def health_check(self) -> bool:
        """检查 Anthropic API 连通性"""
        try:
            client = await self._get_client()
            headers = self._build_headers()
            # 发送一个最小请求来验证连通性
            response = await client.post(
                "/v1/messages",
                headers=headers,
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            return response.status_code in (200, 400)  # 400 也说明连通
        except Exception:
            return False
