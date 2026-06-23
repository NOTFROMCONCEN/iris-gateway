"""Iris AI Gateway - 配置管理"""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Any, List, Optional, Dict, Literal


class Settings(BaseSettings):
    """Iris 网关全局配置"""

    # === 服务配置 ===
    iris_host: str = "0.0.0.0"
    iris_port: int = 8000
    iris_debug: bool = False
    iris_log_level: str = "info"
    iris_environment: Literal["development", "production"] = "development"
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
    memory_backend: Literal["sqlite", "ombre", "none"] = "sqlite"
    memory_db_path: str = "./data/memory/iris.db"
    memory_max_short_term: int = 20
    memory_summary_threshold: int = 10

    # === Ombre-Brain 配置 ===
    ombre_buckets_dir: str = "./data/ombre-brain"
    ombre_dehydration_api_key: Optional[str] = None
    ombre_dehydration_base_url: Optional[str] = None
    ombre_dehydration_model: str = "deepseek-chat"

    # === Ombre-Brain MCP 远程连接 ===
    ombre_mcp_url: Optional[str] = None       # 远程 Ombre-Brain MCP 服务地址
    ombre_mcp_token: Optional[str] = None      # MCP 认证 Token (Bearer)

    # === Redis ===
    redis_url: Optional[str] = None

    # === 感知系统 ===
    perception_enabled: bool = True
    perception_emotion_enabled: bool = True
    perception_intent_enabled: bool = True

    # === 人格配置 ===
    persona_config_dir: str = "./config/personas"

    # === P6: 工具 / SKILL / MCP 代理 ===
    skills_config_dir: str = "./config/skills"
    mcp_tools: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # === 伪装配置 (Claude Code) ===
    claude_disguise_enabled: bool = False
    claude_disguise_user_agent: str = ""
    claude_disguise_extra_headers: Optional[Dict[str, str]] = None

    # === 伪装配置 (OpenAI) ===
    openai_disguise_enabled: bool = False
    openai_disguise_user_agent: str = ""
    openai_disguise_extra_headers: Optional[Dict[str, str]] = None

    # === 默认配置 ===
    default_provider: Literal["openai", "anthropic"] = "openai"
    default_model: str = "kimi-for-coding"
    default_persona: str = "default"
    default_max_tokens: int = 4096
    default_temperature: float = 0.7

    # === 模型发现 ===
    # Kimi 的 OpenAI 兼容接口不支持 /v1/models，关闭自动发现
    provider_model_discovery: bool = False
    available_models: List[Dict[str, str]] = Field(default_factory=lambda: [
        {"id": "kimi-for-coding", "display_name": "Kimi for Coding", "owned_by": "kimi"},
        {"id": "kimi-k2", "display_name": "Kimi K2", "owned_by": "kimi"},
        {"id": "kimi-k2-0711", "display_name": "Kimi K2 (0711)", "owned_by": "kimi"},
        {"id": "moonshot-v1-8k", "display_name": "Moonshot v1 8K", "owned_by": "kimi"},
        {"id": "moonshot-v1-32k", "display_name": "Moonshot v1 32K", "owned_by": "kimi"},
        {"id": "moonshot-v1-128k", "display_name": "Moonshot v1 128K", "owned_by": "kimi"},
    ])
    model_aliases: Dict[str, str] = Field(default_factory=lambda: {
        "coding": "kimi-for-coding",
        "k2": "kimi-k2",
        "k2-0711": "kimi-k2-0711",
        "8k": "moonshot-v1-8k",
        "32k": "moonshot-v1-32k",
        "128k": "moonshot-v1-128k",
    })
    model_providers: Dict[str, str] = Field(default_factory=lambda: {
        "kimi-for-coding": "anthropic",
        "claude-sonnet-4-20250514": "anthropic",
        "kimi-k2": "openai",
        "kimi-k2-0711": "openai",
        "moonshot-v1-8k": "openai",
        "moonshot-v1-32k": "openai",
        "moonshot-v1-128k": "openai",
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
        return self.iris_environment == "production"

    @field_validator("iris_environment", "memory_backend", "default_provider", mode="before")
    @classmethod
    def normalize_enum_strings(cls, value: str) -> str:
        """允许环境变量使用大小写混合写法。"""
        if isinstance(value, str):
            return value.lower().strip()
        return value

    @field_validator("model_providers")
    @classmethod
    def normalize_model_providers(cls, value: Dict[str, str]) -> Dict[str, str]:
        """规范化模型路由表，并拒绝未知 provider。"""
        allowed = {"openai", "anthropic"}
        normalized = {}
        for model, provider in value.items():
            provider_name = provider.lower().strip()
            if provider_name not in allowed:
                raise ValueError(
                    f"model_providers[{model!r}] must be one of {sorted(allowed)}"
                )
            normalized[model] = provider_name
        return normalized


# 全局单例
settings = Settings()
