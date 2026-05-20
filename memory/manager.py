"""Iris AI Gateway - 记忆管理器

管理短期记忆窗口、长期记忆检索和自动摘要。
"""

import asyncio
import logging
from typing import List, Optional, Tuple

from models.schemas import MemoryEntry, MemorySummary, Message, MessageRole
from memory.base import BaseMemoryBackend

logger = logging.getLogger(__name__)


class MemoryManager:
    """记忆管理器"""

    def __init__(
        self,
        backend: BaseMemoryBackend,
        max_short_term: int = 20,
        summary_threshold: int = 10,
    ):
        self.backend = backend
        self.max_short_term = max_short_term
        self.summary_threshold = summary_threshold

    async def get_context(
        self,
        session_id: str,
        persona_id: str,
        current_messages: List[Message],
    ) -> Tuple[List[Message], List[MemorySummary]]:
        """
        获取记忆上下文。

        返回：
        - 增强的消息列表（包含记忆摘要作为 system 消息）
        - 当前记忆摘要列表
        """
        # 并行获取短期记忆和摘要
        short_term_task = self.backend.get_session_messages(
            session_id, persona_id, limit=self.max_short_term
        )
        summaries_task = self.backend.get_summaries(session_id, persona_id)

        short_term, summaries = await asyncio.gather(
            short_term_task, summaries_task
        )

        # 构建增强的消息列表：摘要 system 消息、短期历史、当前请求。
        enhanced_messages = []

        # 如果有记忆摘要，插入为 system 消息
        if summaries:
            summary_text = self._build_summary_prompt(summaries)
            enhanced_messages.append(Message(
                role=MessageRole.SYSTEM,
                content=summary_text,
            ))

        short_term_messages = self._memory_entries_to_messages(short_term)
        enhanced_messages.extend(
            self._filter_duplicate_messages(short_term_messages, current_messages)
        )
        enhanced_messages.extend(current_messages)

        return enhanced_messages, summaries

    async def store_interaction(
        self,
        session_id: str,
        persona_id: str,
        user_message: Message,
        assistant_message: Message,
        perception: Optional[object] = None,
    ):
        """存储一次交互（用户消息 + AI 回复，并行写入）"""
        user_entry = MemoryEntry(
            session_id=session_id,
            persona_id=persona_id,
            role=user_message.role,
            content=user_message.content,
            perception=perception,
        )
        assistant_entry = MemoryEntry(
            session_id=session_id,
            persona_id=persona_id,
            role=assistant_message.role,
            content=assistant_message.content,
        )

        # 并行存储两条消息
        await asyncio.gather(
            self.backend.store(user_entry),
            self.backend.store(assistant_entry),
        )

        logger.debug(f"Stored interaction for session {session_id}")

    async def check_and_summarize(self, session_id: str, persona_id: str) -> bool:
        """检查是否需要生成摘要"""
        # 并行获取消息和摘要
        messages_task = self.backend.get_session_messages(
            session_id, persona_id, limit=1000
        )
        summaries_task = self.backend.get_summaries(session_id, persona_id)

        messages, summaries = await asyncio.gather(
            messages_task, summaries_task
        )

        summarized_count = sum(s.message_count for s in summaries)

        # 如果消息数量超过阈值且未全部摘要
        if len(messages) - summarized_count >= self.summary_threshold:
            return True

        return False

    def _build_summary_prompt(self, summaries: List[MemorySummary]) -> str:
        """构建记忆摘要提示"""
        parts = ["\n# 之前的对话记忆\n"]
        for s in summaries[:3]:  # 最多 3 条摘要
            parts.append(f"## 摘要\n{s.summary}\n")
            if s.key_facts:
                parts.append("关键事实：")
                for fact in s.key_facts:
                    parts.append(f"- {fact}")
                parts.append("")
        return "\n".join(parts)

    @staticmethod
    def _memory_entries_to_messages(entries: List[MemoryEntry]) -> List[Message]:
        """将短期记忆条目转换为可注入的消息"""
        return [
            Message(
                role=entry.role,
                content=entry.content,
                metadata={"memory_entry_id": entry.id},
                timestamp=entry.created_at,
            )
            for entry in entries
        ]

    @staticmethod
    def _filter_duplicate_messages(
        memory_messages: List[Message],
        current_messages: List[Message],
    ) -> List[Message]:
        """避免当客户端已携带历史消息时重复注入相同内容"""
        current_fingerprints = {
            (message.role, message.content)
            for message in current_messages
        }
        return [
            message
            for message in memory_messages
            if (message.role, message.content) not in current_fingerprints
        ]

    async def close(self):
        """关闭记忆管理器"""
        await self.backend.close()
