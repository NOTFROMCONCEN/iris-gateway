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

        # 构建增强的消息列表
        enhanced_messages = list(current_messages)

        # 如果有记忆摘要，插入为 system 消息
        if summaries:
            summary_text = self._build_summary_prompt(summaries)
            enhanced_messages.insert(0, Message(
                role=MessageRole.SYSTEM,
                content=summary_text,
            ))

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

    async def close(self):
        """关闭记忆管理器"""
        await self.backend.close()
