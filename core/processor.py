"""Iris AI Gateway - 核心处理器

将人格注入、记忆检索、感知分析整合为统一的请求处理流程。
通过 _prepare_request() 消除 process/process_stream 的重复代码。
"""

import logging
import time
import uuid
from typing import Optional, Dict, Any, AsyncIterator, Tuple

from models.schemas import ChatRequest, ChatResponse, StreamChunk, Message, MessageRole, PerceptionResult
from core.persona.loader import PersonaLoader
from core.persona.injector import PersonaInjector
from core.perception.analyzer import PerceptionAnalyzer
from memory.manager import MemoryManager
from providers.dispatcher import ProviderDispatcher

logger = logging.getLogger(__name__)


class CoreProcessor:
    """核心处理器 - 请求处理管道"""

    def __init__(
        self,
        dispatcher: ProviderDispatcher,
        persona_loader: PersonaLoader,
        memory_manager: Optional[MemoryManager] = None,
        perception_analyzer: Optional[PerceptionAnalyzer] = None,
        model_aliases: Optional[Dict[str, str]] = None,
        model_providers: Optional[Dict[str, str]] = None,
    ):
        self.dispatcher = dispatcher
        self.persona_loader = persona_loader
        self.persona_injector = PersonaInjector()
        self.memory_manager = memory_manager
        self.perception_analyzer = perception_analyzer
        self.model_aliases = model_aliases or {}
        self.model_providers = {
            model: provider.lower()
            for model, provider in (model_providers or {}).items()
            if provider
        }

    async def _prepare_request(
        self,
        request: ChatRequest,
    ) -> Tuple[ChatRequest, str, str, Optional[PerceptionResult]]:
        """异步公共请求准备管道（含记忆检索）"""
        # 1. 确定会话和用户
        session_id = request.session_id or self._generate_session_id()
        persona_id = request.persona_id or "default"

        # 2. 加载人格
        persona = self.persona_loader.get_persona(persona_id)
        if not persona:
            persona = self.persona_loader.get_default_persona()

        # 3. 感知分析（跳过空消息或极短消息，减少不必要开销）
        perception = None
        if self.perception_analyzer:
            last_msg = request.messages[-1] if request.messages else None
            if last_msg and len(last_msg.content) > 3:
                perception = await self.perception_analyzer.analyze(request.messages)

        # 4. 记忆检索与增强
        messages = list(request.messages)
        if self.memory_manager:
            messages, _ = await self.memory_manager.get_context(
                session_id, persona_id, messages
            )

        # 5. 人格注入
        messages = self.persona_injector.inject(messages, persona)

        # 6. 更新请求
        request_id = f"req-{uuid.uuid4().hex[:8]}"
        model = self.model_aliases.get(request.model, request.model)
        metadata = dict(request.metadata or {})
        metadata["request_id"] = request_id

        if perception:
            metadata["perception"] = perception.model_dump()

        processed_request = request.model_copy(update={
            "messages": messages,
            "session_id": session_id,
            "persona_id": persona_id,
            "model": model,
            "provider": self._resolve_provider(model, request.provider),
            "metadata": metadata,
        })

        return processed_request, session_id, persona_id, perception

    async def process(
        self,
        request: ChatRequest,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> ChatResponse:
        """处理非流式请求"""
        # 公共准备管道
        processed_request, session_id, persona_id, perception = await self._prepare_request(request)

        # 7. 发送到上游 Provider
        response = await self.dispatcher.dispatch(processed_request, extra_headers)

        # 8. 存储记忆
        if self.memory_manager:
            user_msg = request.messages[-1] if request.messages else None
            if user_msg and user_msg.role == MessageRole.USER:
                await self.memory_manager.store_interaction(
                    session_id=session_id,
                    persona_id=persona_id,
                    user_message=user_msg,
                    assistant_message=response.message,
                    perception=perception,
                )

        # 9. 附加感知结果到响应
        if perception:
            response.perception = perception

        return response

    async def process_stream(
        self,
        request: ChatRequest,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> AsyncIterator[StreamChunk]:
        """处理流式请求"""
        # 公共准备管道
        processed_request, session_id, persona_id, perception = await self._prepare_request(request)

        # 流式发送
        full_content = []
        first_chunk = True
        async for chunk in self.dispatcher.dispatch_stream(processed_request, extra_headers):
            full_content.append(chunk.delta)
            # perception 只附加到第一个 chunk，避免重复传输
            if perception and first_chunk:
                chunk.perception = perception
                first_chunk = False
            yield chunk

        # 存储完整回复到记忆
        if self.memory_manager:
            user_msg = request.messages[-1] if request.messages else None
            if user_msg and user_msg.role == MessageRole.USER:
                assistant_message = Message(
                    role=MessageRole.ASSISTANT,
                    content="".join(full_content),
                )
                await self.memory_manager.store_interaction(
                    session_id=session_id,
                    persona_id=persona_id,
                    user_message=user_msg,
                    assistant_message=assistant_message,
                    perception=perception,
                )

    @staticmethod
    def _generate_session_id() -> str:
        """生成会话 ID"""
        return f"sess-{uuid.uuid4().hex[:16]}"

    def _resolve_provider(self, model: Optional[str], requested_provider):
        """根据显式模型配置解析 provider，缺省时保留客户端选择。"""
        from models.schemas import ProviderType

        if model:
            configured_provider = self.model_providers.get(model)
            if configured_provider:
                return ProviderType(configured_provider)

        if requested_provider:
            return requested_provider

        return self._infer_provider_from_model(model)

    @staticmethod
    def _infer_provider_from_model(model: Optional[str]):
        """根据模型名启发式推断 provider，作为显式配置缺失时的兜底。"""
        from models.schemas import ProviderType

        if model and any(kw in model.lower() for kw in ["claude", "anthropic", "kimi-for-coding"]):
            return ProviderType.ANTHROPIC
        return ProviderType.OPENAI
