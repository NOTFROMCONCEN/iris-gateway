"""Iris AI Gateway - 人格系统测试"""

import pytest
from models.schemas import Message, MessageRole, PersonaConfig
from core.persona_injector import PersonaInjector


class TestPersonaInjector:
    """测试人格注入器"""

    def test_inject_persona(self):
        """测试人格注入"""
        injector = PersonaInjector()
        persona = PersonaConfig(
            id="test",
            name="TestBot",
            system_prompt="You are TestBot.",
            speaking_style="Friendly and helpful",
            personality_traits={"friendliness": 0.9},
            response_guidelines=["Be concise"],
        )
        messages = [
            Message(role=MessageRole.USER, content="Hello!"),
        ]

        result = injector.inject(messages, persona)

        assert len(result) == 2
        assert result[0].role == MessageRole.SYSTEM
        assert "TestBot" in result[0].content
        assert "Friendly and helpful" in result[0].content
        assert result[1].content == "Hello!"

    def test_inject_with_existing_system(self):
        """测试已有 system 消息时的注入"""
        injector = PersonaInjector()
        persona = PersonaConfig(
            id="test",
            name="TestBot",
            system_prompt="You are TestBot.",
        )
        messages = [
            Message(role=MessageRole.SYSTEM, content="Existing system prompt."),
            Message(role=MessageRole.USER, content="Hello!"),
        ]

        result = injector.inject(messages, persona)

        assert result[0].role == MessageRole.SYSTEM
        assert "TestBot" in result[0].content
        assert "Existing system prompt" in result[0].content
