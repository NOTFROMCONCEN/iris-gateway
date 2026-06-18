"""Iris AI Gateway - 核心处理器测试"""

import asyncio

from core.processor import CoreProcessor
from models.schemas import ChatRequest, Message, MessageRole, PersonaConfig, ProviderType


class FakePersonaLoader:
    """用于 CoreProcessor 单测的人格加载器"""

    def get_persona(self, persona_id: str):
        return None

    def get_default_persona(self):
        return PersonaConfig(
            id="default",
            name="Iris",
            system_prompt="You are Iris.",
        )


def test_prepare_request_applies_model_alias_and_provider():
    processor = CoreProcessor(
        dispatcher=None,
        persona_loader=FakePersonaLoader(),
        model_aliases={"sonnet": "claude-sonnet-4-20250514"},
        model_providers={"claude-sonnet-4-20250514": "anthropic"},
    )
    request = ChatRequest(
        model="sonnet",
        provider=ProviderType.OPENAI,
        messages=[Message(role=MessageRole.USER, content="Hello")],
    )

    processed, _, _, _ = asyncio.run(processor._prepare_request(request))

    assert processed.model == "claude-sonnet-4-20250514"
    assert processed.provider == ProviderType.ANTHROPIC


def test_prepare_request_does_not_mutate_original_metadata():
    processor = CoreProcessor(
        dispatcher=None,
        persona_loader=FakePersonaLoader(),
        model_providers={"gpt-4o": "openai"},
    )
    request = ChatRequest(
        model="gpt-4o",
        messages=[Message(role=MessageRole.USER, content="Hello")],
        metadata={"client": "opencode"},
    )

    processed, _, _, _ = asyncio.run(processor._prepare_request(request))

    assert request.metadata == {"client": "opencode"}
    assert processed.metadata["client"] == "opencode"
    assert processed.metadata["request_id"].startswith("req-")


def test_prepare_request_uses_configured_provider_for_non_obvious_model_name():
    processor = CoreProcessor(
        dispatcher=None,
        persona_loader=FakePersonaLoader(),
        model_providers={"internal-coder": "anthropic"},
    )
    request = ChatRequest(
        model="internal-coder",
        messages=[Message(role=MessageRole.USER, content="Hello")],
    )

    processed, _, _, _ = asyncio.run(processor._prepare_request(request))

    assert processed.provider == ProviderType.ANTHROPIC
