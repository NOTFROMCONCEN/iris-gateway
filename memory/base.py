"""Iris AI Gateway - 记忆存储抽象基类"""

import abc
from typing import List, Optional

from models.schemas import MemoryEntry, MemorySummary


class BaseMemoryBackend(abc.ABC):
    """记忆存储后端抽象基类"""

    @abc.abstractmethod
    async def store(self, entry: MemoryEntry) -> str:
        """存储记忆条目，返回条目 ID"""
        ...

    @abc.abstractmethod
    async def get_session_messages(
        self,
        session_id: str,
        persona_id: str,
        limit: int = 20,
    ) -> List[MemoryEntry]:
        """获取会话的最近 N 条消息（短期记忆）"""
        ...

    @abc.abstractmethod
    async def get_summaries(
        self,
        session_id: str,
        persona_id: str,
    ) -> List[MemorySummary]:
        """获取会话的记忆摘要"""
        ...

    @abc.abstractmethod
    async def store_summary(self, summary: MemorySummary) -> str:
        """存储记忆摘要"""
        ...

    @abc.abstractmethod
    async def close(self):
        """关闭后端连接"""
        ...
