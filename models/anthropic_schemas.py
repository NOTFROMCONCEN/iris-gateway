"""Iris AI Gateway - Anthropic API 兼容数据模型"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, Union
import time
import uuid


# === 请求模型 ===

class AnthropicImageContent(BaseModel):
    """Anthropic 图片内容块"""
    type: Literal["image"] = "image"
    source: Dict[str, Any]


class AnthropicTextContent(BaseModel):
    """Anthropic 文本内容块"""
    type: Literal["text"] = "text"
    text: str


class AnthropicToolUseContent(BaseModel):
    """Anthropic 工具使用内容块"""
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: Dict[str, Any]


class AnthropicToolResultContent(BaseModel):
    """Anthropic 工具结果内容块"""
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: Optional[Union[str, List[Dict[str, Any]]]] = None
    is_error: Optional[bool] = None


class AnthropicThinkingContent(BaseModel):
    """Anthropic 思考内容块"""
    type: Literal["thinking"] = "thinking"
    thinking: str


# 内容块联合类型
AnthropicContentBlock = Union[
    AnthropicTextContent,
    AnthropicImageContent,
    AnthropicToolUseContent,
    AnthropicToolResultContent,
    AnthropicThinkingContent,
]


class AnthropicMessage(BaseModel):
    """Anthropic 格式消息"""
    role: Literal["user", "assistant"]
    content: Union[str, List[AnthropicContentBlock]]


class AnthropicCacheControl(BaseModel):
    """缓存控制"""
    type: str = "ephemeral"


class AnthropicSystemMessage(BaseModel):
    """Anthropic 系统消息块"""
    type: Literal["text"] = "text"
    text: str
    cache_control: Optional[AnthropicCacheControl] = None


class AnthropicTool(BaseModel):
    """Anthropic 工具定义"""
    name: str
    description: Optional[str] = None
    input_schema: Dict[str, Any]


class AnthropicMessageRequest(BaseModel):
    """Anthropic Messages API 请求格式"""
    model: str = "claude-sonnet-4-20250514"
    messages: List[AnthropicMessage]
    max_tokens: int = 4096
    system: Optional[Union[str, List[AnthropicSystemMessage]]] = None
    metadata: Optional[Dict[str, Any]] = None
    stop_sequences: Optional[List[str]] = None
    stream: bool = False
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    tools: Optional[List[AnthropicTool]] = None
    tool_choice: Optional[Union[Literal["auto", "any", "none"], Dict[str, Any]]] = None


# === 响应模型 ===

class AnthropicTextDelta(BaseModel):
    """文本增量"""
    type: Literal["text_delta"] = "text_delta"
    text: str


class AnthropicThinkingDelta(BaseModel):
    """思考增量"""
    type: Literal["thinking_delta"] = "thinking_delta"
    thinking: str


class AnthropicInputJsonDelta(BaseModel):
    """工具输入 JSON 增量"""
    type: Literal["input_json_delta"] = "input_json_delta"
    partial_json: str = ""


class AnthropicUsage(BaseModel):
    """Anthropic 用量统计"""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None


class AnthropicContentBlock(BaseModel):
    """Anthropic 响应内容块"""
    type: str  # "text", "tool_use", "thinking"
    text: Optional[str] = None
    id: Optional[str] = None
    name: Optional[str] = None
    input: Optional[Dict[str, Any]] = None
    thinking: Optional[str] = None


class AnthropicMessageResponse(BaseModel):
    """Anthropic Messages API 响应格式"""
    id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:24]}")
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    model: str = ""
    content: List[AnthropicContentBlock] = Field(default_factory=list)
    stop_reason: Optional[Literal["end_turn", "max_tokens", "stop_sequence", "tool_use"]] = None
    stop_sequence: Optional[str] = None
    usage: AnthropicUsage = Field(default_factory=AnthropicUsage)


# === 流式事件模型 ===

class AnthropicMessageStartEvent(BaseModel):
    """message_start 事件"""
    type: Literal["message_start"] = "message_start"
    message: AnthropicMessageResponse


class AnthropicContentBlockStartEvent(BaseModel):
    """content_block_start 事件"""
    type: Literal["content_block_start"] = "content_block_start"
    index: int
    content_block: AnthropicContentBlock


class AnthropicContentBlockDeltaEvent(BaseModel):
    """content_block_delta 事件"""
    type: Literal["content_block_delta"] = "content_block_delta"
    index: int
    delta: Union[AnthropicTextDelta, AnthropicThinkingDelta, AnthropicInputJsonDelta]


class AnthropicContentBlockStopEvent(BaseModel):
    """content_block_stop 事件"""
    type: Literal["content_block_stop"] = "content_block_stop"
    index: int


class AnthropicMessageDeltaEvent(BaseModel):
    """message_delta 事件"""
    type: Literal["message_delta"] = "message_delta"
    delta: Dict[str, Any]  # stop_reason, stop_sequence
    usage: Dict[str, int]  # output_tokens


class AnthropicMessageStopEvent(BaseModel):
    """message_stop 事件"""
    type: Literal["message_stop"] = "message_stop"


class AnthropicPingEvent(BaseModel):
    """ping 事件"""
    type: Literal["ping"] = "ping"


class AnthropicErrorEvent(BaseModel):
    """error 事件"""
    type: Literal["error"] = "error"
    error: Dict[str, Any]


# === 模型列表 ===

class AnthropicModelInfo(BaseModel):
    """Anthropic 模型信息"""
    id: str
    display_name: str
    created_at: Optional[str] = None


class AnthropicModelListResponse(BaseModel):
    """Anthropic 模型列表响应"""
    data: List[AnthropicModelInfo] = Field(default_factory=list)
    has_more: bool = False
    first_id: Optional[str] = None
    last_id: Optional[str] = None
