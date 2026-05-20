"""Iris AI Gateway - OpenAI 伪装器"""

import logging
from typing import Dict, Optional

from disguise.config import OpenAIDisguiseConfig

logger = logging.getLogger(__name__)


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
