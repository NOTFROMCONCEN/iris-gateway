"""Iris AI Gateway - 伪装配置"""

from pydantic import BaseModel, Field
from typing import Dict, Optional


class DisguiseConfig(BaseModel):
    """伪装配置"""
    enabled: bool = False
    user_agent: str = ""
    extra_headers: Dict[str, str] = Field(default_factory=dict)


class ClaudeCodeDisguiseConfig(DisguiseConfig):
    """Claude Code 伪装配置"""
    # 默认模拟 Claude Code 的请求特征
    enabled: bool = False
    user_agent: str = "ClaudeCode/0.2.32 (darwin; arm64)"
    extra_headers: Dict[str, str] = Field(default_factory=lambda: {
        "X-Stainless-Arch": "arm64",
        "X-Stainless-Lang": "python",
        "X-Stainless-OS": "Mac OS",
        "X-Stainless-Runtime": "CPython",
        "X-Stainless-Runtime-Version": "3.11.7",
        "X-Stainless-Package-Version": "0.46.0",
        "anthropic-beta": "prompt-caching-2024-07-31,computer-use-2024-10-22",
    })
    # Claude Code 的 anthropic-version
    anthropic_version: str = "2023-06-01"


class OpenAIDisguiseConfig(DisguiseConfig):
    """OpenAI 伪装配置"""
    enabled: bool = False
    user_agent: str = ""
    extra_headers: Dict[str, str] = Field(default_factory=dict)
