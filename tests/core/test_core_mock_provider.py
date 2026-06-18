"""Iris AI Gateway - mock provider 核心路径测试"""

import asyncio

from core.processor import CoreProcessor
from models.schemas import ChatRequest, ChatResponse, Message, MessageRole, PersonaConfig, ProviderType


class FakePersonaLoader:
    """用于核心处理器测试的人格加载器"""

    def get_persona(self, persona_id: str):
        return None

    def get_default_persona(self):
        return PersonaConfig(
            id="default",
            name="Iris",
            system_prompt="You are Iris.",
        )


class FakeDispatcher:
    """不访问真实上游 API 的 Provider 调度器"""

    def __init__(self):
        self.last_request = None

    async def dispatch(self, request, extra_headers=None):
        self.last_request = request
        return ChatResponse(
            message=Message(role=MessageRole.ASSISTANT, content="mock response"),
            provider=ProviderType.OPENAI,
            model=request.model,
            persona_id=request.persona_id,
            session_id=request.session_id,
        )


def test_core_processor_can_run_with_mock_provider():
    dispatcher = FakeDispatcher()
    processor = CoreProcessor(
        dispatcher=dispatcher,
        persona_loader=FakePersonaLoader(),
    )
    request = ChatRequest(
        model="gpt-4o",
        provider=ProviderType.OPENAI,
        messages=[Message(role=MessageRole.USER, content="Hello")],
    )

    response = asyncio.run(processor.process(request))

    assert response.message.content == "mock response"
    assert dispatcher.last_request.messages[0].role == MessageRole.SYSTEM
    assert dispatcher.last_request.messages[-1].content == "Hello"
