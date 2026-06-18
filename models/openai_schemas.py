"""Iris AI Gateway - OpenAI API 兼容数据模型"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, Union
from enum import Enum
import time
import uuid


# === 请求模型 ===

class OpenAIMessage(BaseModel):
    """OpenAI 格式消息"""
    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[Union[str, List[Dict[str, Any]]]] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class OpenAIChatRequest(BaseModel):
    """OpenAI Chat Completions 请求格式"""
    model: str = "gpt-4o"
    messages: List[OpenAIMessage]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: Optional[int] = 1
    stream: bool = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    max_completion_tokens: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    response_format: Optional[Dict[str, Any]] = None
    seed: Optional[int] = None
    reasoning_effort: Optional[Union[Literal["low", "medium", "high"], Dict[str, Any]]] = None


# === 响应模型 ===

class OpenAIChoice(BaseModel):
    """OpenAI 响应选择项"""
    index: int = 0
    message: Optional[OpenAIMessage] = None
    delta: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None


class OpenAIUsage(BaseModel):
    """OpenAI 用量统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OpenAIChatResponse(BaseModel):
    """OpenAI Chat Completions 响应格式"""
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = ""
    choices: List[OpenAIChoice] = Field(default_factory=list)
    usage: Optional[OpenAIUsage] = None


class OpenAIStreamChunk(BaseModel):
    """OpenAI 流式响应块"""
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = ""
    choices: List[OpenAIChoice] = Field(default_factory=list)


class OpenAIModelInfo(BaseModel):
    """OpenAI 模型信息"""
    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "iris-gateway"


class OpenAIModelListResponse(BaseModel):
    """OpenAI 模型列表响应"""
    object: str = "list"
    data: List[OpenAIModelInfo] = Field(default_factory=list)
