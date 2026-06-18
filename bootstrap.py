"""Iris AI Gateway - 应用启动引导

将组件初始化逻辑从 main.py 中提取，保持入口文件简洁。
"""

import logging
import os
import time

from config.settings import settings
from utils.logging import setup_logging
from core.protocol_converter import ProtocolConverter
from core.persona.loader import PersonaLoader
from core.perception.analyzer import PerceptionAnalyzer
from core.processor import CoreProcessor
from providers.dispatcher import ProviderDispatcher
from disguise import ClaudeCodeDisguise, OpenAIDisguise, ClaudeCodeDisguiseConfig, OpenAIDisguiseConfig
from memory.backends.sqlite_backend import SQLiteMemoryBackend
from memory.backends.ombre_adapter import OmbreBrainBackend
from memory.backends.ombre_mcp_client import OmbreMCPClient
from memory.manager import MemoryManager

logger = logging.getLogger(__name__)


def init_logging():
    """初始化日志系统"""
    setup_logging(settings.iris_log_level)
    logger.info("=" * 60)
    logger.info("Iris AI Gateway starting up...")
    logger.info("Version: 0.1.0")
    logger.info(f"Debug: {settings.iris_debug}")
    logger.info(f"Host: {settings.iris_host}:{settings.iris_port}")
    logger.info("=" * 60)


def check_auth_config():
    """检查认证配置"""
    if not settings.api_key_list:
        message = "IRIS_API_KEYS is empty; gateway requests will not require authentication"
        if settings.is_production:
            raise RuntimeError(f"{message}. Refusing to start in production.")
        logger.warning(message)


def init_converter() -> ProtocolConverter:
    """初始化协议转换器"""
    converter = ProtocolConverter()
    logger.info("Protocol converter initialized")
    return converter


def init_persona_loader() -> PersonaLoader:
    """初始化人格加载器"""
    loader = PersonaLoader(config_dir=settings.persona_config_dir)
    personas = loader.list_personas()
    logger.info(f"Personas loaded: {[p['name'] for p in personas]}")
    return loader


def init_memory_manager() -> MemoryManager | None:
    """初始化记忆管理器"""
    if settings.memory_backend == "sqlite":
        backend = SQLiteMemoryBackend(db_path=settings.memory_db_path)
        manager = MemoryManager(
            backend=backend,
            max_short_term=settings.memory_max_short_term,
            summary_threshold=settings.memory_summary_threshold,
        )
        logger.info(f"Memory manager initialized (SQLite: {settings.memory_db_path})")
        return manager
    elif settings.memory_backend == "ombre":
        if settings.ombre_mcp_url:
            backend = OmbreMCPClient(
                mcp_url=settings.ombre_mcp_url,
                mcp_token=settings.ombre_mcp_token,
            )
            manager = MemoryManager(
                backend=backend,
                max_short_term=settings.memory_max_short_term,
                summary_threshold=settings.memory_summary_threshold,
            )
            logger.info(f"Memory manager initialized (Ombre-Brain MCP @ {settings.ombre_mcp_url})")
            return manager
        else:
            backend = OmbreBrainBackend(
                buckets_dir=settings.ombre_buckets_dir,
                dehydration_api_key=settings.ombre_dehydration_api_key,
                dehydration_base_url=settings.ombre_dehydration_base_url,
                dehydration_model=settings.ombre_dehydration_model,
            )
            manager = MemoryManager(
                backend=backend,
                max_short_term=settings.memory_max_short_term,
                summary_threshold=settings.memory_summary_threshold,
            )
            logger.info(f"Memory manager initialized (Ombre-Brain local: {settings.ombre_buckets_dir})")
            return manager
    else:
        logger.info("Memory manager disabled")
        return None


def init_perception_analyzer() -> PerceptionAnalyzer | None:
    """初始化感知分析器"""
    if settings.perception_enabled:
        analyzer = PerceptionAnalyzer(enabled=settings.perception_enabled)
        logger.info("Perception analyzer initialized")
        return analyzer
    else:
        logger.info("Perception analyzer disabled")
        return None


def init_dispatcher() -> ProviderDispatcher:
    """初始化 Provider 调度器"""
    dispatcher = ProviderDispatcher(
        anthropic_api_key=settings.anthropic_api_key,
        anthropic_base_url=settings.anthropic_base_url,
        anthropic_auth_header=settings.anthropic_auth_header,
        openai_api_key=settings.openai_api_key,
        openai_base_url=settings.openai_base_url,
        openai_organization=settings.openai_organization,
        timeout=settings.upstream_timeout,
        max_retries=settings.upstream_max_retries,
        retry_delay=settings.upstream_retry_delay,
    )
    return dispatcher


def init_processor(
    dispatcher: ProviderDispatcher,
    persona_loader: PersonaLoader,
    memory_manager: MemoryManager | None,
    perception_analyzer: PerceptionAnalyzer | None,
) -> CoreProcessor:
    """初始化核心处理器"""
    processor = CoreProcessor(
        dispatcher=dispatcher,
        persona_loader=persona_loader,
        memory_manager=memory_manager,
        perception_analyzer=perception_analyzer,
        model_aliases=settings.model_aliases,
        model_providers=settings.model_providers,
    )
    logger.info("Core processor initialized")
    return processor


def init_disguise():
    """初始化伪装层，返回 (claude_disguise, openai_disguise) 元组"""
    claude_config = ClaudeCodeDisguiseConfig(enabled=settings.claude_disguise_enabled)
    if settings.claude_disguise_user_agent:
        claude_config.user_agent = settings.claude_disguise_user_agent
    if settings.claude_disguise_extra_headers:
        claude_config.extra_headers = settings.claude_disguise_extra_headers
    claude_disguise = ClaudeCodeDisguise(config=claude_config)
    logger.info(f"Claude disguise: {'enabled' if claude_config.enabled else 'disabled'}")

    openai_config = OpenAIDisguiseConfig(enabled=settings.openai_disguise_enabled)
    if settings.openai_disguise_user_agent:
        openai_config.user_agent = settings.openai_disguise_user_agent
    if settings.openai_disguise_extra_headers:
        openai_config.extra_headers = settings.openai_disguise_extra_headers
    openai_disguise = OpenAIDisguise(config=openai_config)
    logger.info(f"OpenAI disguise: {'enabled' if openai_config.enabled else 'disabled'}")

    return claude_disguise, openai_disguise


def ensure_data_dirs():
    """确保数据目录存在"""
    os.makedirs(os.path.dirname(settings.memory_db_path) or ".", exist_ok=True)


def bootstrap(app):
    """执行完整的应用启动引导，将所有组件挂载到 app.state"""
    startup_start = time.monotonic()

    init_logging()
    check_auth_config()

    app.state.converter = init_converter()
    app.state.persona_loader = init_persona_loader()
    app.state.memory_manager = init_memory_manager()
    app.state.perception_analyzer = init_perception_analyzer()
    app.state.dispatcher = init_dispatcher()

    app.state.processor = init_processor(
        dispatcher=app.state.dispatcher,
        persona_loader=app.state.persona_loader,
        memory_manager=app.state.memory_manager,
        perception_analyzer=app.state.perception_analyzer,
    )

    app.state.claude_disguise, app.state.openai_disguise = init_disguise()
    app.state.available_models = settings.available_models
    logger.info(f"Available models: {len(settings.available_models)}")

    ensure_data_dirs()

    startup_elapsed = time.monotonic() - startup_start
    logger.info(f"Iris AI Gateway ready! (startup took {startup_elapsed:.2f}s)")
    logger.info("=" * 60)


async def shutdown(app):
    """执行应用关闭清理"""
    logger.info("Shutting down Iris AI Gateway...")
    if hasattr(app.state, "dispatcher"):
        await app.state.dispatcher.close()
    if hasattr(app.state, "memory_manager") and app.state.memory_manager:
        await app.state.memory_manager.close()
    logger.info("Goodbye!")
