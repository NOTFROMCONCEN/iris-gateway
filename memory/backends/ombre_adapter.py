"""Iris AI Gateway - Ombre-Brain 记忆系统适配器

将 Ombre-Brain (https://github.com/P0lar1zzZ/Ombre-Brain) 集成到 Iris Gateway
作为长期情感记忆后端，替代简单的 SQLite 记忆系统。

特性：
- Russell 效价/唤醒度情感坐标
- Obsidian Markdown 存储
- 艾宾浩斯遗忘曲线
- 权重池主动浮现
- 双链自动注入
"""

import logging
import os
import sys
import asyncio
import importlib.util
from typing import List, Optional, Dict, Any
from datetime import datetime

from memory.base import BaseMemoryBackend
from models.schemas import MemoryEntry, MemorySummary, Message, MessageRole

logger = logging.getLogger(__name__)

# Ombre-Brain 模块路径（不污染 sys.path，避免 utils.py 冲突）
_OMBRE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "external", "ombre-brain")
_OMBRE_MODULES = {}  # 缓存已加载的模块
_OMBRE_ORIGINAL_NAMES = ["utils", "bucket_manager", "dehydrator", "decay_engine"]
_SAVED_MODULES = {}  # 保存被覆盖的原始模块


def _load_ombre_module(name: str):
    """按文件路径加载 Ombre-Brain 模块，避免全局 sys.path 污染"""
    if name in _OMBRE_MODULES:
        return _OMBRE_MODULES[name]

    file_path = os.path.join(_OMBRE_PATH, f"{name}.py")
    if not os.path.exists(file_path):
        raise ImportError(f"Ombre-Brain module not found: {file_path}")

    spec = importlib.util.spec_from_file_location(f"ombre_brain.{name}", file_path)
    mod = importlib.util.module_from_spec(spec)

    # 保存原始模块（如果存在），防止被永久覆盖
    if name in sys.modules and name not in _SAVED_MODULES:
        _SAVED_MODULES[name] = sys.modules[name]

    # 注册到 sys.modules：
    # ombre_brain.{name} — 带前缀的安全名称（永久保留）
    # {name} — 原始名称，Ombre-Brain 内部交叉引用需要（临时）
    sys.modules[f"ombre_brain.{name}"] = mod
    sys.modules[name] = mod

    spec.loader.exec_module(mod)
    _OMBRE_MODULES[name] = mod
    return mod


def _restore_iris_modules():
    """恢复被 Ombre-Brain 覆盖的 Iris 原始模块"""
    for name, original_mod in _SAVED_MODULES.items():
        sys.modules[name] = original_mod
    # 清理 Ombre-Brain 的原始名称注册（保留 ombre_brain.{name} 前缀版本）
    for name in _OMBRE_ORIGINAL_NAMES:
        if name not in _SAVED_MODULES:
            sys.modules.pop(name, None)


class OmbreBrainBackend(BaseMemoryBackend):
    """Ombre-Brain 记忆存储后端适配器"""

    def __init__(
        self,
        buckets_dir: str = "./data/ombre-brain",
        config_override: Optional[Dict[str, Any]] = None,
        dehydration_api_key: Optional[str] = None,
        dehydration_base_url: Optional[str] = None,
        dehydration_model: str = "deepseek-chat",
    ):
        """
        初始化 Ombre-Brain 适配器

        Args:
            buckets_dir: 记忆桶存储目录
            config_override: 覆盖默认配置
            dehydration_api_key: 脱水压缩 API Key
            dehydration_base_url: 脱水压缩 API 地址
            dehydration_model: 脱水压缩模型
        """
        self.buckets_dir = buckets_dir
        self.config_override = config_override or {}
        self.dehydration_api_key = dehydration_api_key
        self.dehydration_base_url = dehydration_base_url
        self.dehydration_model = dehydration_model

        self._bucket_mgr = None
        self._dehydrator = None
        self._decay_engine = None
        self._initialized = False

    async def _ensure_init(self):
        """延迟初始化（避免在 import 时加载 heavy deps）"""
        if self._initialized:
            return

        try:
            # 按依赖顺序加载：utils → bucket_manager → dehydrator → decay_engine
            utils_mod = _load_ombre_module("utils")
            bm_mod = _load_ombre_module("bucket_manager")
            dehy_mod = _load_ombre_module("dehydrator")
            decay_mod = _load_ombre_module("decay_engine")

            BucketManager = bm_mod.BucketManager
            Dehydrator = dehy_mod.Dehydrator
            DecayEngine = decay_mod.DecayEngine

            # 所有 Ombre-Brain 模块已加载完毕，恢复 Iris 原始模块
            _restore_iris_modules()
        except (ImportError, FileNotFoundError) as e:
            logger.error(f"Failed to import Ombre-Brain modules: {e}")
            _restore_iris_modules()  # 确保即使失败也恢复
            raise RuntimeError(
                "Ombre-Brain not found. Please clone it to external/ombre-brain:\n"
                "  git clone https://github.com/P0lar1zzZ/Ombre-Brain.git external/ombre-brain"
            )

        # 构建配置
        config = {
            "buckets_dir": self.buckets_dir,
            "merge_threshold": 75,
            "scoring_weights": {
                "topic_relevance": 4.0,
                "emotion_resonance": 2.0,
                "time_proximity": 1.5,
                "importance": 1.0,
            },
            "matching": {
                "fuzzy_threshold": 50,
                "max_results": 5,
            },
            "wikilink": {
                "enabled": True,
                "use_tags": False,
                "use_domain": True,
                "use_auto_keywords": True,
                "auto_top_k": 8,
                "min_keyword_len": 2,
                "exclude_keywords": [],
            },
            "decay": {
                "lambda": 0.05,
                "threshold": 0.3,
                "check_interval_hours": 24,
                "emotion_weights": {"base": 1.0, "arousal_boost": 0.8},
            },
            "dehydration": {
                "model": self.dehydration_model,
                "base_url": self.dehydration_base_url or "https://api.deepseek.com/v1",
                "max_tokens": 1024,
                "temperature": 0.1,
            },
            "log_level": "INFO",
        }
        # 应用用户覆盖
        self._deep_merge(config, self.config_override)

        # 设置 API Key 环境变量
        if self.dehydration_api_key:
            os.environ["OMBRE_API_KEY"] = self.dehydration_api_key

        self._bucket_mgr = BucketManager(config)
        self._dehydrator = Dehydrator(config)
        self._decay_engine = DecayEngine(config, self._bucket_mgr)

        # 启动衰减引擎（后台任务）
        await self._decay_engine.start()

        self._initialized = True
        logger.info(f"Ombre-Brain initialized: {self.buckets_dir}")

    @staticmethod
    def _deep_merge(base: dict, override: dict):
        """深度合并字典"""
        for key, val in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(val, dict):
                OmbreBrainBackend._deep_merge(base[key], val)
            else:
                base[key] = val

    # === BaseMemoryBackend 接口实现 ===

    async def store(self, entry: MemoryEntry) -> str:
        """存储记忆条目为 Ombre-Brain 记忆桶"""
        await self._ensure_init()

        # 将 Iris MemoryEntry 转换为 Ombre-Brain 桶格式
        # 提取情感和元数据
        valence = 0.5
        arousal = 0.3
        importance = 5
        tags = []
        domain = ["对话"]
        bucket_type = "dynamic"

        if entry.perception:
            # 映射 Iris 感知结果到 Russell 情感坐标
            valence, arousal = self._map_emotion_to_valence_arousal(entry.perception.emotion)
            # 紧急度映射到 importance
            importance = max(1, min(10, int(5 + entry.perception.urgency * 5)))
            if entry.perception.keywords:
                tags = entry.perception.keywords[:5]
            if entry.perception.intent:
                domain = [entry.perception.intent.value]

        # 在 name 中编码 role 和 session_id（frontmatter 不受 wikilink 影响）
        name = f"iris_{entry.role.value}_{entry.session_id[:8]}"

        # 纯内容写入 body（避免 wikilink 破坏结构化标记）
        content = entry.content

        # 将 Iris 元数据序列化为 tags，便于后续检索
        extra_tags = []
        if entry.session_id:
            extra_tags.append(f"session:{entry.session_id[:8]}")
        if entry.persona_id:
            extra_tags.append(f"persona:{entry.persona_id}")
        tags = list(dict.fromkeys(tags + extra_tags))  # 去重保持顺序

        # 创建桶
        bucket_id = await self._bucket_mgr.create(
            content=content,
            tags=tags,
            importance=importance,
            domain=domain,
            valence=valence,
            arousal=arousal,
            bucket_type=bucket_type,
            name=name,
        )

        logger.debug(f"Stored memory as bucket: {bucket_id}")
        return bucket_id

    async def get_session_messages(
        self,
        session_id: str,
        persona_id: str,
        limit: int = 20,
    ) -> List[MemoryEntry]:
        """
        获取会话的最近 N 条消息。
        通过遍历所有桶，匹配 name 中编码的 session_id。
        """
        await self._ensure_init()

        session_suffix = f"_{session_id[:8]}"
        all_buckets = await self._bucket_mgr.list_all(include_archive=False)

        entries = []
        for bucket in all_buckets:
            meta = bucket.get("metadata", {})
            name = meta.get("name", "")
            # name 格式: iris_{role}_{session_id[:8]}
            if name.endswith(session_suffix):
                entry = self._bucket_to_memory_entry(bucket, session_id, persona_id)
                if entry:
                    entries.append(entry)

        # 按创建时间排序，取最近 limit 条
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries[:limit]

    async def get_summaries(
        self,
        session_id: str,
        persona_id: str,
    ) -> List[MemorySummary]:
        """获取记忆摘要 — 返回未解决的高权重记忆"""
        await self._ensure_init()

        # 使用 breath 逻辑：浮现未解决记忆
        all_buckets = await self._bucket_mgr.list_all(include_archive=False)

        summaries = []
        for bucket in all_buckets:
            meta = bucket.get("metadata", {})
            if meta.get("resolved"):
                continue

            # 构建摘要
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
                created_at=datetime.fromisoformat(meta.get("created", datetime.now().isoformat())),
            ))

        # 按重要性排序
        summaries.sort(key=lambda s: s.message_count, reverse=True)
        return summaries[:5]

    async def store_summary(self, summary: MemorySummary) -> str:
        """存储记忆摘要为永久桶"""
        await self._ensure_init()

        content = f"# 记忆摘要\n\n{summary.summary}\n\n"
        if summary.key_facts:
            content += "## 关键事实\n" + "\n".join(f"- {f}" for f in summary.key_facts)

        bucket_id = await self._bucket_mgr.create(
            content=content,
            tags=["summary", "自动归档"],
            importance=8,
            domain=["摘要"],
            valence=0.5,
            arousal=0.2,
            bucket_type="permanent",
            name=f"摘要_{summary.session_id[:8]}",
        )
        return bucket_id

    async def close(self):
        """关闭 Ombre-Brain"""
        if self._decay_engine:
            await self._decay_engine.stop()
            logger.info("Ombre-Brain decay engine stopped")

    # === 额外功能：情感记忆搜索 ===

    async def search_by_emotion(
        self,
        query: str,
        valence: Optional[float] = None,
        arousal: Optional[float] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """按情感坐标搜索记忆"""
        await self._ensure_init()
        return await self._bucket_mgr.search(
            query=query,
            limit=limit,
            query_valence=valence,
            query_arousal=arousal,
        )

    async def surface_memories(self, limit: int = 5) -> List[Dict[str, Any]]:
        """浮现未解决的高权重记忆（类似 breath 工具）"""
        await self._ensure_init()

        all_buckets = await self._bucket_mgr.list_all(include_archive=False)
        active = []

        for bucket in all_buckets:
            meta = bucket.get("metadata", {})
            if meta.get("resolved") or meta.get("archived"):
                continue

            # 简单权重计算（类似 Ombre 衰减公式）
            importance = meta.get("importance", 5)
            arousal = meta.get("arousal", 0.3)
            activation_count = meta.get("activation_count", 1)

            # 高唤醒度 + 高重要性 = 更可能浮现
            weight = importance * (1 + arousal) * (activation_count ** 0.3)
            active.append((weight, bucket))

        active.sort(key=lambda x: x[0], reverse=True)
        return [b for _, b in active[:limit]]

    # === 内部工具方法 ===

    @staticmethod
    def _map_emotion_to_valence_arousal(emotion) -> tuple:
        """映射 Iris EmotionType 到 Russell 情感坐标 (valence, arousal)"""
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
    def _build_bucket_content(entry: MemoryEntry) -> str:
        """构建记忆桶内容（已弃用，内容直接存纯文本）"""
        return entry.content

    @staticmethod
    def _bucket_to_memory_entry(bucket: dict, session_id: str, persona_id: str) -> Optional[MemoryEntry]:
        """将 Ombre-Brain 桶转换回 Iris MemoryEntry"""
        meta = bucket.get("metadata", {})
        content = bucket.get("content", "")

        # 从 name 中提取角色信息（name 格式: iris_{role}_{session_id[:8]}）
        role = MessageRole.USER
        name = meta.get("name", "")
        if "iris_assistant_" in name:
            role = MessageRole.ASSISTANT
        elif "iris_system_" in name:
            role = MessageRole.SYSTEM

        # 如果 content 还包含旧版结构化标记，尝试提取纯内容
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
            created_at=datetime.fromisoformat(meta.get("created", datetime.now().isoformat())),
            metadata={
                "valence": meta.get("valence"),
                "arousal": meta.get("arousal"),
                "domain": meta.get("domain"),
                "tags": meta.get("tags"),
                "source": "ombre-brain",
            },
        )
