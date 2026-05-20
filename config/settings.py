"""Iris AI Gateway - 配置管理"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional, Dict


class Settings(BaseSettings):
    """Iris 网关全局配置"""

    # === 服务配置 ===
    iris_host: str = "0.0.0.0"
    iris_port: int = 8000
    iris_debug: bool = False
    iris_log_level: str = "info"
    iris_environment: str = "development"  # development | production
    cors_origins: str = "*"

    # === API 密钥 ===
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # === 上游 Provider 配置 ===
    anthropic_base_url: Optional[str] = None
    anthropic_auth_header: str = "x-api-key"  # moonshot 兼容层用 "api-key"
    openai_base_url: Optional[str] = None
    openai_organization: Optional[str] = None
    upstream_timeout: int = 120
    upstream_max_retries: int = 3
    upstream_retry_delay: float = 1.0

    # === 网关认证 ===
    iris_api_keys: str = ""  # 逗号分隔的 API Key 列表

    # === 记忆系统 ===
    memory_backend: str = "sqlite"  # sqlite | ombre
    memory_db_path: str = "./data/memory/iris.db"
    memory_max_short_term: int = 20
    memory_summary_threshold: int = 10

    # === Ombre-Brain 配置 ===
    ombre_buckets_dir: str = "./data/ombre-brain"
    ombre_dehydration_api_key: Optional[str] = None
    ombre_dehydration_base_url: Optional[str] = None
    ombre_dehydration_model: str = "deepseek-chat"

    # === Redis ===
    redis_url: Optional[str] = None

    # === 感知系统 ===
    perception_enabled: bool = True
    perception_emotion_enabled: bool = True
    perception_intent_enabled: bool = True

    # === 人格配置 ===
    persona_config_dir: str = "./config/personas"

    # === 伪装配置 (Claude Code) ===
    claude_disguise_enabled: bool = False
    claude_disguise_user_agent: str = ""
    claude_disguise_extra_headers: Optional[Dict[str, str]] = None

    # === 伪装配置 (OpenAI) ===
    openai_disguise_enabled: bool = False
    openai_disguise_user_agent: str = ""
    openai_disguise_extra_headers: Optional[Dict[str, str]] = None

    # === 默认配置 ===
    default_provider: str = "openai"
    default_model: str = "gpt-4o"
    default_persona: str = "default"
    default_max_tokens: int = 4096
    default_temperature: float = 0.7
    available_models: List[Dict[str, str]] = Field(default_factory=lambda: [
        {"id": "gpt-4o", "display_name": "GPT-4o", "owned_by": "openai"},
        {"id": "gpt-4o-mini", "display_name": "GPT-4o Mini", "owned_by": "openai"},
        {"id": "claude-sonnet-4-20250514", "display_name": "Claude Sonnet 4", "owned_by": "anthropic"},
        {"id": "claude-opus-4-20250514", "display_name": "Claude Opus 4", "owned_by": "anthropic"},
        {"id": "claude-haiku-4-20250514", "display_name": "Claude Haiku 4", "owned_by": "anthropic"},
    ])
    model_aliases: Dict[str, str] = Field(default_factory=lambda: {
        "claude-sonnet-4": "claude-sonnet-4-20250514",
        "claude-opus-4": "claude-opus-4-20250514",
        "claude-haiku-4": "claude-haiku-4-20250514",
    })

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @property
    def api_key_list(self) -> List[str]:
        """获取 API Key 列表"""
        if not self.iris_api_keys:
            return []
        return [k.strip() for k in self.iris_api_keys.split(",") if k.strip()]

    @property
    def cors_origin_list(self) -> List[str]:
        """获取 CORS origin 列表"""
        if not self.cors_origins:
            return []
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        """是否生产环境"""
        return self.iris_environment.lower() == "production"


# 全局单例
settings = Settings()
