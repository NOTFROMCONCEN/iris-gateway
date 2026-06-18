"""Iris AI Gateway - Ombre-Brain MCP 远程客户端

通过 HTTP 调用远程部署的 Ombre-Brain MCP 服务，而非本地加载模块。
适用于将 Ombre-Brain 作为独立 MCP 服务器部署的场景。
"""

import logging
import os
from typing import List, Optional, Dict, Any
from datetime import datetime

import httpx

from memory.base import BaseMemoryBackend
from models.schemas import MemoryEntry, MemorySummary, Message, MessageRole

logger = logging.getLogger(__name__)


class OmbreMCPClient(BaseMemoryBackend):
    """Ombre-Brain 远程 MCP 客户端适配器

    通过 HTTP JSON-RPC 协议与远端 Ombre-Brain MCP 服务通信。
    """

    def __init__(
        self,
        mcp_url: str,
        mcp_token: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Args:
            mcp_url: Ombre-Brain MCP 服务地址，如 http://192.168.31.120:18001/mcp
            mcp_token: 认证 Token（Authorization header 值，含 Bearer 前缀）
            timeout: HTTP 请求超时（秒）
        """
        self.mcp_url = mcp_url.rstrip("/")
        self.mcp_token = mcp_token
        self.timeout = timeout

        self._client: Optional[httpx.AsyncClient] = None
        self._request_id = 0

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.mcp_token:
                headers["Authorization"] = self.mcp_token
            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _rpc_call(self, method: str, params: dict = None) -> dict:
        """执行 JSON-RPC 调用"""
        client = await self._get_client()
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        try:
            resp = await client.post(self.mcp_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"MCP RPC error: {data['error']}")
            return data.get("result", {})
        except httpx.HTTPError as e:
            logger.error(f"MCP HTTP error calling {method}: {e}")
            raise RuntimeError(f"Ombre MCP connection failed: {e}")

    async def _call_tool(self, tool_name: str, arguments: dict = None) -> dict:
        """调用 Ombre-Brain MCP 工具

        MCP 工具调用格式: tools/call 方法，参数为 {name, arguments}
        """
        result = await self._rpc_call("tools/call", {
            "name": tool_name,
            "arguments": arguments or {},
        })
        # 解析工具返回内容
        if isinstance(result, dict):
            content = result.get("content", [])
            if isinstance(content, list) and len(content) > 0:
                first = content[0]
                if isinstance(first, dict) and "text" in first:
                    return {"text": first["text"], "raw": result}
            return result
        return {"text": str(result), "raw": result}

    # === BaseMemoryBackend 接口实现 ===

    async def store(self, entry: MemoryEntry) -> str:
        """存储记忆条目"""
        tags = []
        if entry.perception and entry.perception.keywords:
            tags = entry.perception.keywords[:5]
        if entry.session_id:
            tags.append(f"session:{entry.session_id[:8]}")
        if entry.persona_id:
            tags.append(f"persona:{entry.persona_id}")

        importance = 5
        valence = 0.5
        arousal = 0.3
        domain = ["对话"]

        if entry.perception:
            valence, arousal = self._map_emotion_to_valence_arousal(entry.perception.emotion)
            importance = max(1, min(10, int(5 + entry.perception.urgency * 5)))
            if entry.perception.intent:
                domain = [entry.perception.intent.value]

        name = f"iris_{entry.role.value}_{entry.session_id[:8]}"

        result = await self._call_tool("create_memory", {
            "content": entry.content,
            "tags": tags,
            "importance": importance,
            "domain": domain,
            "valence": valence,
            "arousal": arousal,
            "bucket_type": "dynamic",
            "name": name,
        })

        bucket_id = ""
        if isinstance(result, dict):
            bucket_id = result.get("text", "") or str(result.get("raw", {}).get("id", ""))
        logger.debug(f"Stored memory via MCP: {bucket_id}")
        return bucket_id

    async def get_session_messages(
        self,
        session_id: str,
        persona_id: str,
        limit: int = 20,
    ) -> List[MemoryEntry]:
        """获取会话的最近 N 条消息"""
        session_suffix = f"_{session_id[:8]}"

        result = await self._call_tool("list_memories", {
            "include_archive": False,
            "limit": 200,
        })

        buckets = self._extract_buckets(result)
        entries = []
        for bucket in buckets:
            meta = bucket.get("metadata", {})
            name = meta.get("name", "")
            if name.endswith(session_suffix):
                entry = self._bucket_to_memory_entry(bucket, session_id, persona_id)
                if entry:
                    entries.append(entry)

        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries[:limit]

    async def get_summaries(
        self,
        session_id: str,
        persona_id: str,
    ) -> List[MemorySummary]:
        """获取记忆摘要 — 通过 breath 工具浮现高权重记忆"""
        result = await self._call_tool("breath", {"limit": 10})

        buckets = self._extract_buckets(result)
        summaries = []
        for bucket in buckets:
            meta = bucket.get("metadata", {})
            if meta.get("resolved") or meta.get("archived"):
                continue

            summary_text = meta.get("name", "未命名记忆")
            content = bucket.get("content", "")[:200]
            if content:
                summary_text += f": {content}"

            key_facts = [
                f"情感: valence={meta.get('valence', 0.5):.2f}, arousal={meta.get('arousal', 0.3):.2f}",
                f"重要性: {meta.get('importance', 5)}/10",
                f"域: {', '.join(meta.get('domain', ['未分类']))}",
            ]

            summaries.append(MemorySummary(
                id=meta.get("id", ""),
                session_id=session_id,
                persona_id=persona_id,
                summary=summary_text,
                key_facts=key_facts,
                message_count=meta.get("activation_count", 1),
                created_at=datetime.fromisoformat(
                    meta.get("created", datetime.now().isoformat())
                ),
            ))

        summaries.sort(key=lambda s: s.message_count, reverse=True)
        return summaries[:5]

    async def store_summary(self, summary: MemorySummary) -> str:
        """存储记忆摘要为永久桶"""
        content = f"# 记忆摘要\n\n{summary.summary}\n\n"
        if summary.key_facts:
            content += "## 关键事实\n" + "\n".join(f"- {f}" for f in summary.key_facts)

        result = await self._call_tool("create_memory", {
            "content": content,
            "tags": ["summary", "自动归档"],
            "importance": 8,
            "domain": ["摘要"],
            "valence": 0.5,
            "arousal": 0.2,
            "bucket_type": "permanent",
            "name": f"摘要_{summary.session_id[:8]}",
        })

        bucket_id = result.get("text", "") if isinstance(result, dict) else str(result)
        return bucket_id

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Ombre MCP client closed")

    # === 额外功能 ===

    async def search_by_emotion(
        self,
        query: str,
        valence: Optional[float] = None,
        arousal: Optional[float] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """按情感坐标搜索记忆"""
        args = {"query": query, "limit": limit}
        if valence is not None:
            args["query_valence"] = valence
        if arousal is not None:
            args["query_arousal"] = arousal

        result = await self._call_tool("search_memories", args)
        return self._extract_buckets(result)

    async def surface_memories(self, limit: int = 5) -> List[Dict[str, Any]]:
        """浮现未解决的高权重记忆"""
        result = await self._call_tool("breath", {"limit": limit})
        return self._extract_buckets(result)

    # === 内部工具方法 ===

    @staticmethod
    def _extract_buckets(result: dict) -> list:
        """从 MCP 返回结果中提取桶列表"""
        # MCP 可能返回 {text: "..."} 或直接的 bucket 列表
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # 尝试从 raw 中获取
            raw = result.get("raw", {})
            content = raw.get("content", [])
            for item in content:
                if isinstance(item, dict) and item.get("type") == "resource":
                    resource = item.get("resource", {})
                    buckets = resource.get("buckets", resource.get("memories", []))
                    if buckets:
                        return buckets
            # 尝试 text 字段 (可能含 JSON)
            text = result.get("text", "")
            if text:
                import json
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        return parsed
                    if isinstance(parsed, dict):
                        return parsed.get("buckets", parsed.get("memories", []))
                except (json.JSONDecodeError, TypeError):
                    pass
        return []

    @staticmethod
    def _map_emotion_to_valence_arousal(emotion) -> tuple:
        """映射 Iris EmotionType 到 Russell 情感坐标"""
        mapping = {
            "happy": (0.8, 0.7),
            "sad": (0.2, 0.3),
            "angry": (0.2, 0.9),
            "surprised": (0.5, 0.9),
            "fearful": (0.1, 0.8),
            "curious": (0.7, 0.6),
            "empathetic": (0.7, 0.5),
            "neutral": (0.5, 0.3),
        }
        key = emotion.value if hasattr(emotion, "value") else str(emotion).lower()
        return mapping.get(key, (0.5, 0.3))

    @staticmethod
    def _bucket_to_memory_entry(bucket: dict, session_id: str, persona_id: str) -> Optional[MemoryEntry]:
        """将 Ombre-Brain 桶转换回 Iris MemoryEntry"""
        meta = bucket.get("metadata", {})
        content = bucket.get("content", "")

        role = MessageRole.USER
        name = meta.get("name", "")
        if "iris_assistant_" in name:
            role = MessageRole.ASSISTANT
        elif "iris_system_" in name:
            role = MessageRole.SYSTEM

        clean_content = content
        if "## 内容" in content:
            lines = content.splitlines()
            content_start = -1
            content_end = len(lines)
            for i, line in enumerate(lines):
                if line.strip() == "## 内容":
                    content_start = i + 1
                elif content_start >= 0 and line.strip() in ("## 元数据", "---"):
                    content_end = i
                    break
            if content_start >= 0:
                clean_content = "\n".join(lines[content_start:content_end]).strip()

        return MemoryEntry(
            id=meta.get("id", ""),
            session_id=session_id,
            persona_id=persona_id,
            role=role,
            content=clean_content or content,
            importance=meta.get("importance", 5) / 10.0,
            created_at=datetime.fromisoformat(
                meta.get("created", datetime.now().isoformat())
            ),
            metadata={
                "valence": meta.get("valence"),
                "arousal": meta.get("arousal"),
                "domain": meta.get("domain"),
                "tags": meta.get("tags"),
                "source": "ombre-mcp-remote",
            },
        )
