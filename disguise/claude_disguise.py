"""Iris AI Gateway - Claude Code 伪装器

模拟 Claude Code CLI 的请求特征，包括 Headers、User-Agent 等。
"""

import logging
from typing import Dict, Optional

from disguise.config import ClaudeCodeDisguiseConfig

logger = logging.getLogger(__name__)


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
