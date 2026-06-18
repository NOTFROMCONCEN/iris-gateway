"""Iris AI Gateway - OpenAI 上游 Provider

负责调用 OpenAI Chat Completions API，继承 BaseProvider 的连接池和重试机制。
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


class OpenAIProvider(BaseProvider):
    """OpenAI 上游 Provider"""

    DEFAULT_BASE_URL = "https://api.openai.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 120,
        organization: Optional[str] = None,
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
        self.organization = organization

    def _build_headers(self, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key or ''}",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _build_request_body(self, request: ChatRequest) -> Dict[str, Any]:
        """将内部 ChatRequest 转换为 OpenAI API 请求体"""
        messages = []
        for msg in request.messages:
            content = msg.content
            if msg.metadata and msg.metadata.get("openai_content"):
                content = msg.metadata["openai_content"]
            msg_dict: Dict[str, Any] = {
                "role": msg.role.value,
                "content": content,
            }
            if msg.name:
                msg_dict["name"] = msg.name
            # 处理工具调用元数据
            if msg.metadata:
                if "tool_calls" in msg.metadata and msg.metadata["tool_calls"]:
                    msg_dict["tool_calls"] = msg.metadata["tool_calls"]
                if "tool_call_id" in msg.metadata and msg.metadata["tool_call_id"]:
                    msg_dict["tool_call_id"] = msg.metadata["tool_call_id"]
            messages.append(msg_dict)

        body: Dict[str, Any] = {
            "model": request.model,
            "messages": messages,
        }

        max_completion_tokens = request.metadata.get("max_completion_tokens")
        if max_completion_tokens:
            body["max_completion_tokens"] = max_completion_tokens
        elif request.max_tokens:
            body["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.top_p is not None:
            body["top_p"] = request.top_p
        if request.stream:
            body["stream"] = True

        # 处理 stop
        stop = request.metadata.get("stop")
        if stop:
            body["stop"] = stop

        # 处理额外参数
        for key in ("presence_penalty", "frequency_penalty", "seed", "n", "response_format", "logit_bias"):
            val = request.metadata.get(key)
            if val is not None:
                body[key] = val

        # 处理 tools
        if request.tools:
            body["tools"] = request.tools
            tool_choice = request.metadata.get("tool_choice")
            if tool_choice:
                body["tool_choice"] = tool_choice

        # 处理 user
        user = request.metadata.get("user")
        if user:
            body["user"] = user

        return body

    async def chat(self, request: ChatRequest, extra_headers: Optional[Dict[str, str]] = None) -> ChatResponse:
        """非流式调用 OpenAI API（带重试）"""
        client = await self._get_client()
        headers = self._build_headers(extra_headers)
        body = self._build_request_body(request)

        async def _do_request():
            response = await client.post("/v1/chat/completions", headers=headers, json=body)
            response.raise_for_status()
            return self._parse_response(response.json(), request)

        try:
            return await self._retry_request(_do_request, "OpenAI chat")
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"OpenAI request failed: {e}")
            raise

    async def chat_stream(self, request: ChatRequest, extra_headers: Optional[Dict[str, str]] = None) -> AsyncIterator[StreamChunk]:
        """流式调用 OpenAI API"""
        client = await self._get_client()
        headers = self._build_headers(extra_headers)
        body = self._build_request_body(request)
        body["stream"] = True

        msg_id = f"iris-{uuid.uuid4().hex[:12]}"

        try:
            async with client.stream("POST", "/v1/chat/completions", headers=headers, json=body) as response:
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
                            chunk = self._parse_stream_chunk(data, msg_id, request.model)
                            if chunk:
                                yield chunk
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse SSE data: {data_str}")
                            continue

        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI stream error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"OpenAI stream failed: {e}")
            raise

    def _parse_response(self, data: Dict[str, Any], request: ChatRequest) -> ChatResponse:
        """解析 OpenAI 响应为内部格式"""
        content = ""
        metadata: Dict[str, Any] = {}
        choices = data.get("choices", [])
        if choices:
            choice = choices[0]
            message = choice.get("message", {})
            content = message.get("content", "") or ""
            if message.get("tool_calls"):
                metadata["tool_calls"] = message["tool_calls"]
            if choice.get("finish_reason"):
                metadata["finish_reason"] = choice["finish_reason"]

        usage_data = data.get("usage", {})
        return ChatResponse(
            id=data.get("id", f"iris-{uuid.uuid4().hex[:12]}"),
            message=Message(
                role=MessageRole.ASSISTANT,
                content=content,
                metadata=metadata or None,
            ),
            provider=ProviderType.OPENAI,
            model=data.get("model", request.model),
            persona_id=request.persona_id or "default",
            session_id=request.session_id or "",
            usage={
                "prompt_tokens": usage_data.get("prompt_tokens", 0),
                "completion_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0),
            },
        )

    def _parse_stream_chunk(self, data: Dict[str, Any], msg_id: str, model: str) -> Optional[StreamChunk]:
        """解析 OpenAI SSE 块为内部 StreamChunk"""
        choices = data.get("choices", [])
        if not choices:
            return None

        choice = choices[0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")

        content = delta.get("content", "")

        # 跳过空内容且无 finish_reason 的块
        if not content and not finish_reason:
            return None

        return StreamChunk(
            id=data.get("id", msg_id),
            delta=content,
            provider=ProviderType.OPENAI,
            model=data.get("model", model),
            finish_reason=finish_reason,
        )

    async def health_check(self) -> bool:
        """检查 OpenAI API 连通性"""
        try:
            client = await self._get_client()
            headers = self._build_headers()
            response = await client.get("/v1/models", headers=headers)
            return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[Dict[str, Any]]:
        """获取 OpenAI 上游模型列表

        OpenAI 兼容格式: data: [{id, owned_by, ...}]
        """
        try:
            client = await self._get_client()
            headers = self._build_headers()
            response = await client.get("/v1/models", headers=headers)
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                return [
                    {
                        "id": m.get("id", ""),
                        "display_name": m.get("id", ""),
                        "owned_by": m.get("owned_by", "openai"),
                    }
                    for m in models if m.get("id")
                ]
        except Exception as e:
            logger.warning(f"Failed to list OpenAI models from {self.base_url}: {e}")
        return []
