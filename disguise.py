"""Iris AI Gateway - 伪装层

合并 Claude Code 和 OpenAI 伪装功能为单文件。
模拟上游工具的请求特征，绕过调用源限制。
"""

import logging
from typing import Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# === 伪装配置 ===

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


# === 伪装器 ===

class ClaudeCodeDisguise:
    """Claude Code 伪装器"""

    def __init__(self, config: Optional[ClaudeCodeDisguiseConfig] = None):
        self.config = config or ClaudeCodeDisguiseConfig()

    def apply(self, headers: Dict[str, str]) -> Dict[str, str]:
        """将伪装 Headers 应用到请求头"""
        if not self.config.enabled:
            return headers

        disguised = dict(headers)

        # 应用 User-Agent
        if self.config.user_agent:
            disguised["User-Agent"] = self.config.user_agent

        # 应用额外 Headers
        for key, value in self.config.extra_headers.items():
            disguised[key] = value

        logger.debug(f"Applied Claude Code disguise: User-Agent={self.config.user_agent}")
        return disguised

    def get_headers(self) -> Dict[str, str]:
        """获取伪装 Headers"""
        if not self.config.enabled:
            return {}

        headers = {}
        if self.config.user_agent:
            headers["User-Agent"] = self.config.user_agent
        headers.update(self.config.extra_headers)
        return headers


class OpenAIDisguise:
    """OpenAI 伪装器"""

    def __init__(self, config: Optional[OpenAIDisguiseConfig] = None):
        self.config = config or OpenAIDisguiseConfig()

    def apply(self, headers: Dict[str, str]) -> Dict[str, str]:
        """将伪装 Headers 应用到请求头"""
        if not self.config.enabled:
            return headers

        disguised = dict(headers)

        if self.config.user_agent:
            disguised["User-Agent"] = self.config.user_agent

        for key, value in self.config.extra_headers.items():
            disguised[key] = value

        return disguised

    def get_headers(self) -> Dict[str, str]:
        """获取伪装 Headers"""
        if not self.config.enabled:
            return {}

        headers = {}
        if self.config.user_agent:
            headers["User-Agent"] = self.config.user_agent
        headers.update(self.config.extra_headers)
        return headers
