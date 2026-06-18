"""Iris AI Gateway - 统一数据模型"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from datetime import datetime
import uuid


# === 枚举类型 ===

class ProviderType(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class EmotionType(str, Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    FEARFUL = "fearful"
    CURIOUS = "curious"
    EMPATHETIC = "empathetic"


class IntentType(str, Enum):
    QUESTION = "question"
    COMMAND = "command"
    CONVERSATION = "conversation"
    CREATIVE = "creative"
    ANALYSIS = "analysis"
    EMOTIONAL_SUPPORT = "emotional_support"
    INFORMATION = "information"
    CODE = "code"


# === 消息模型 ===

class Message(BaseModel):
    """统一消息模型"""
    role: MessageRole
    content: str
    name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ToolCall(BaseModel):
    """工具调用"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    arguments: Dict[str, Any]


class ToolResult(BaseModel):
    """工具结果"""
    tool_call_id: str
    content: str
    success: bool = True


# === 感知模型 ===

class PerceptionResult(BaseModel):
    """感知分析结果"""
    emotion: EmotionType = EmotionType.NEUTRAL
    emotion_confidence: float = 0.0
    intent: IntentType = IntentType.CONVERSATION
    intent_confidence: float = 0.0
    keywords: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    urgency: float = 0.0  # 0.0 ~ 1.0
    sentiment: float = 0.0  # -1.0 ~ 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# === 记忆模型 ===

class MemoryEntry(BaseModel):
    """记忆条目"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    persona_id: str
    role: MessageRole
    content: str
    perception: Optional[PerceptionResult] = None
    importance: float = 0.5  # 0.0 ~ 1.0
    embedding: Optional[List[float]] = None
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemorySummary(BaseModel):
    """记忆摘要"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    persona_id: str
    summary: str
    key_facts: List[str] = Field(default_factory=list)
    message_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)


# === 人格模型 ===

class PersonaConfig(BaseModel):
    """人格配置"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Iris"
    description: str = "一个友好、智能的AI助手"
    system_prompt: str = ""
    personality_traits: Dict[str, float] = Field(default_factory=lambda: {
        "friendliness": 0.8,
        "formality": 0.5,
        "creativity": 0.7,
        "empathy": 0.8,
        "humor": 0.6,
        "verbosity": 0.5,
    })
    speaking_style: str = "自然、友好、有条理"
    knowledge_domains: List[str] = Field(default_factory=list)
    forbidden_topics: List[str] = Field(default_factory=list)
    default_emotion: EmotionType = EmotionType.FRIENDLY if hasattr(EmotionType, 'FRIENDLY') else EmotionType.NEUTRAL
    response_guidelines: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# === API 请求/响应模型 ===

class ChatRequest(BaseModel):
    """统一聊天请求"""
    messages: List[Message]
    model: Optional[str] = None
    provider: Optional[ProviderType] = None
    persona_id: Optional[str] = None
    session_id: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    stream: bool = False
    tools: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """统一聊天响应"""
    id: str = Field(default_factory=lambda: f"iris-{uuid.uuid4().hex[:12]}")
    message: Message
    provider: ProviderType
    model: str
    persona_id: str
    session_id: str
    perception: Optional[PerceptionResult] = None
    usage: Dict[str, int] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


class StreamChunk(BaseModel):
    """流式响应块"""
    id: str
    delta: str
    provider: ProviderType
    model: str
    finish_reason: Optional[str] = None
    perception: Optional[PerceptionResult] = None
    usage: Optional[Dict[str, int]] = None
    thinking: Optional[str] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


# === 会话模型 ===

class Session(BaseModel):
    """会话"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    persona_id: str
    provider: ProviderType = ProviderType.OPENAI
    model: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# === 健康检查 ===

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    version: str = "0.1.0"
    providers: Dict[str, bool] = Field(default_factory=dict)
    memory_backend: str = "sqlite"
    uptime: float = 0.0
