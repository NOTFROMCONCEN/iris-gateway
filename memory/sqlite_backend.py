"""Iris AI Gateway - SQLite 记忆存储后端"""

import logging
import os
from datetime import datetime
from typing import List, Optional

import aiosqlite

from models.schemas import MemoryEntry, MemorySummary, MessageRole
from memory.base import BaseMemoryBackend

logger = logging.getLogger(__name__)


class SQLiteMemoryBackend(BaseMemoryBackend):
    """SQLite 记忆存储后端"""

    def __init__(self, db_path: str = "./data/memory/iris.db"):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def _get_db(self) -> aiosqlite.Connection:
        """获取或创建数据库连接"""
        if self._db is None:
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            self._db = await aiosqlite.connect(self.db_path)
            self._db.row_factory = aiosqlite.Row
            await self._init_tables()
        return self._db

    async def _init_tables(self):
        """初始化数据库表"""
        db = self._db
        await db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                persona_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                perception TEXT,
                importance REAL DEFAULT 0.5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_session 
            ON memories(session_id, persona_id, created_at DESC)
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                persona_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                key_facts TEXT,
                message_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_summaries_session 
            ON summaries(session_id, persona_id, created_at DESC)
        """)
        await db.commit()

    async def store(self, entry: MemoryEntry) -> str:
        """存储记忆条目"""
        db = await self._get_db()
        perception_json = None
        if entry.perception:
            import json
            perception_json = json.dumps(entry.perception.model_dump())

        metadata_json = None
        if entry.metadata:
            import json
            metadata_json = json.dumps(entry.metadata)

        await db.execute(
            """
            INSERT INTO memories (id, session_id, persona_id, role, content, perception, importance, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.session_id,
                entry.persona_id,
                entry.role.value,
                entry.content,
                perception_json,
                entry.importance,
                entry.created_at.isoformat(),
                metadata_json,
            ),
        )
        await db.commit()
        return entry.id

    async def get_session_messages(
        self,
        session_id: str,
        persona_id: str,
        limit: int = 20,
    ) -> List[MemoryEntry]:
        """获取会话的最近 N 条消息"""
        db = await self._get_db()
        async with db.execute(
            """
            SELECT * FROM memories 
            WHERE session_id = ? AND persona_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, persona_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()

        entries = []
        for row in reversed(rows):  # 按时间正序排列
            entries.append(self._row_to_entry(row))
        return entries

    async def get_summaries(
        self,
        session_id: str,
        persona_id: str,
    ) -> List[MemorySummary]:
        """获取会话的记忆摘要"""
        db = await self._get_db()
        async with db.execute(
            """
            SELECT * FROM summaries 
            WHERE session_id = ? AND persona_id = ?
            ORDER BY created_at DESC
            LIMIT 5
            """,
            (session_id, persona_id),
        ) as cursor:
            rows = await cursor.fetchall()

        summaries = []
        for row in rows:
            import json
            key_facts = []
            if row["key_facts"]:
                try:
                    key_facts = json.loads(row["key_facts"])
                except json.JSONDecodeError:
                    pass
            summaries.append(MemorySummary(
                id=row["id"],
                session_id=row["session_id"],
                persona_id=row["persona_id"],
                summary=row["summary"],
                key_facts=key_facts,
                message_count=row["message_count"],
                created_at=datetime.fromisoformat(row["created_at"]),
            ))
        return summaries

    async def store_summary(self, summary: MemorySummary) -> str:
        """存储记忆摘要"""
        db = await self._get_db()
        import json
        key_facts_json = json.dumps(summary.key_facts)

        await db.execute(
            """
            INSERT INTO summaries (id, session_id, persona_id, summary, key_facts, message_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                summary.id,
                summary.session_id,
                summary.persona_id,
                summary.summary,
                key_facts_json,
                summary.message_count,
                summary.created_at.isoformat(),
            ),
        )
        await db.commit()
        return summary.id

    async def close(self):
        """关闭数据库连接"""
        if self._db:
            await self._db.close()
            self._db = None

    @staticmethod
    def _row_to_entry(row) -> MemoryEntry:
        """将数据库行转换为 MemoryEntry"""
        import json
        perception = None
        if row["perception"]:
            try:
                from models.schemas import PerceptionResult
                perception = PerceptionResult(**json.loads(row["perception"]))
            except (json.JSONDecodeError, Exception):
                pass

        metadata = {}
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except json.JSONDecodeError:
                pass

        return MemoryEntry(
            id=row["id"],
            session_id=row["session_id"],
            persona_id=row["persona_id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            perception=perception,
            importance=row["importance"],
            created_at=datetime.fromisoformat(row["created_at"]),
            metadata=metadata,
        )
