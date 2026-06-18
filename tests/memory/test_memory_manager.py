"""Iris AI Gateway - 记忆管理器测试"""

import asyncio
from typing import List

from memory.base import BaseMemoryBackend
from memory.manager import MemoryManager
from models.schemas import MemoryEntry, MemorySummary, Message, MessageRole


class FakeMemoryBackend(BaseMemoryBackend):
    """用于 MemoryManager 单测的内存后端"""

    def __init__(
        self,
        messages: List[MemoryEntry] | None = None,
        summaries: List[MemorySummary] | None = None,
    ):
        self.messages = messages or []
        self.summaries = summaries or []

    async def store(self, entry: MemoryEntry) -> str:
        self.messages.append(entry)
        return entry.id

    async def get_session_messages(
        self,
        session_id: str,
        persona_id: str,
        limit: int = 20,
    ) -> List[MemoryEntry]:
        return self.messages[-limit:]

    async def get_summaries(
        self,
        session_id: str,
        persona_id: str,
    ) -> List[MemorySummary]:
        return self.summaries

    async def store_summary(self, summary: MemorySummary) -> str:
        self.summaries.append(summary)
        return summary.id

    async def close(self):
        return None


def test_get_context_without_memory_returns_current_messages():
    backend = FakeMemoryBackend()
    manager = MemoryManager(backend)
    current = [Message(role=MessageRole.USER, content="现在的问题")]

    messages, summaries = asyncio.run(
        manager.get_context("session-1", "default", current)
    )

    assert summaries == []
    assert messages == current


def test_get_context_injects_short_term_memory_before_current_messages():
    backend = FakeMemoryBackend(messages=[
        MemoryEntry(
            session_id="session-1",
            persona_id="default",
            role=MessageRole.USER,
            content="之前的问题",
        ),
        MemoryEntry(
            session_id="session-1",
            persona_id="default",
            role=MessageRole.ASSISTANT,
            content="之前的回答",
        ),
    ])
    manager = MemoryManager(backend)
    current = [Message(role=MessageRole.USER, content="现在的问题")]

    messages, _ = asyncio.run(
        manager.get_context("session-1", "default", current)
    )

    assert [message.content for message in messages] == [
        "之前的问题",
        "之前的回答",
        "现在的问题",
    ]
    assert messages[0].metadata["memory_entry_id"]


def test_get_context_injects_summary_before_short_term_memory():
    backend = FakeMemoryBackend(
        messages=[
            MemoryEntry(
                session_id="session-1",
                persona_id="default",
                role=MessageRole.USER,
                content="之前的问题",
            ),
        ],
        summaries=[
            MemorySummary(
                session_id="session-1",
                persona_id="default",
                summary="用户正在调试网关。",
                key_facts=["偏好中文沟通"],
                message_count=4,
            ),
        ],
    )
    manager = MemoryManager(backend)
    current = [Message(role=MessageRole.USER, content="现在的问题")]

    messages, summaries = asyncio.run(
        manager.get_context("session-1", "default", current)
    )

    assert len(summaries) == 1
    assert messages[0].role == MessageRole.SYSTEM
    assert "用户正在调试网关。" in messages[0].content
    assert [message.content for message in messages[1:]] == [
        "之前的问题",
        "现在的问题",
    ]


def test_get_context_skips_memory_already_sent_by_client():
    backend = FakeMemoryBackend(messages=[
        MemoryEntry(
            session_id="session-1",
            persona_id="default",
            role=MessageRole.USER,
            content="客户端已经带上的历史问题",
        ),
    ])
    manager = MemoryManager(backend)
    current = [
        Message(role=MessageRole.USER, content="客户端已经带上的历史问题"),
        Message(role=MessageRole.USER, content="现在的问题"),
    ]

    messages, _ = asyncio.run(
        manager.get_context("session-1", "default", current)
    )

    assert messages == current
