"""Iris AI Gateway - FastAPI 主入口

统一 AI 网关，兼容 OpenAI 和 Anthropic API 协议。
支持人格系统、记忆系统、感知能力，以及上游伪装功能。
"""

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from utils.logging import setup_logging
from core.protocol_converter import ProtocolConverter
from core.persona_loader import PersonaLoader
from core.perception_analyzer import PerceptionAnalyzer
from core.processor import CoreProcessor
from providers.dispatcher import ProviderDispatcher
from disguise.claude_disguise import ClaudeCodeDisguise
from disguise.openai_disguise import OpenAIDisguise
from disguise.config import ClaudeCodeDisguiseConfig, OpenAIDisguiseConfig
from memory.sqlite_backend import SQLiteMemoryBackend
from memory.ombre_adapter import OmbreBrainBackend
from memory.manager import MemoryManager
from middleware.auth import AuthMiddleware
from utils.exceptions import IrisGatewayError
from api import openai, anthropic, health

logger = logging.getLogger(__name__)


# === 可用模型列表 ===
AVAILABLE_MODELS = [
    {"id": "gpt-4o", "display_name": "GPT-4o", "owned_by": "openai"},
    {"id": "gpt-4o-mini", "display_name": "GPT-4o Mini", "owned_by": "openai"},
    {"id": "claude-sonnet-4-20250514", "display_name": "Claude Sonnet 4", "owned_by": "anthropic"},
    {"id": "claude-opus-4-20250514", "display_name": "Claude Opus 4", "owned_by": "anthropic"},
    {"id": "claude-haiku-4-20250514", "display_name": "Claude Haiku 4", "owned_by": "anthropic"},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    startup_start = time.monotonic()
    setup_logging(settings.iris_log_level)
    logger.info("=" * 60)
    logger.info("Iris AI Gateway starting up...")
    logger.info("Version: 0.1.0")
    logger.info(f"Debug: {settings.iris_debug}")
    logger.info(f"Host: {settings.iris_host}:{settings.iris_port}")
    logger.info("=" * 60)

    # 初始化协议转换器
    app.state.converter = ProtocolConverter()
    logger.info("Protocol converter initialized")

    # 初始化人格加载器
    app.state.persona_loader = PersonaLoader(config_dir=settings.persona_config_dir)
    personas = app.state.persona_loader.list_personas()
    logger.info(f"Personas loaded: {[p['name'] for p in personas]}")

    # 初始化记忆管理器
    app.state.memory_manager = None
    if settings.memory_backend == "sqlite":
        backend = SQLiteMemoryBackend(db_path=settings.memory_db_path)
        app.state.memory_manager = MemoryManager(
            backend=backend,
            max_short_term=settings.memory_max_short_term,
            summary_threshold=settings.memory_summary_threshold,
        )
        logger.info(f"Memory manager initialized (SQLite: {settings.memory_db_path})")
    elif settings.memory_backend == "ombre":
        backend = OmbreBrainBackend(
            buckets_dir=settings.ombre_buckets_dir,
            dehydration_api_key=settings.ombre_dehydration_api_key,
            dehydration_base_url=settings.ombre_dehydration_base_url,
            dehydration_model=settings.ombre_dehydration_model,
        )
        app.state.memory_manager = MemoryManager(
            backend=backend,
            max_short_term=settings.memory_max_short_term,
            summary_threshold=settings.memory_summary_threshold,
        )
        logger.info(f"Memory manager initialized (Ombre-Brain: {settings.ombre_buckets_dir})")
    else:
        logger.info("Memory manager disabled")

    # 初始化感知分析器
    app.state.perception_analyzer = None
    if settings.perception_enabled:
        app.state.perception_analyzer = PerceptionAnalyzer(
            enabled=settings.perception_enabled,
        )
        logger.info("Perception analyzer initialized")
    else:
        logger.info("Perception analyzer disabled")

    # 初始化 Provider 调度器
    app.state.dispatcher = ProviderDispatcher(
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

    # 初始化核心处理器
    app.state.processor = CoreProcessor(
        dispatcher=app.state.dispatcher,
        persona_loader=app.state.persona_loader,
        memory_manager=app.state.memory_manager,
        perception_analyzer=app.state.perception_analyzer,
    )
    logger.info("Core processor initialized")

    # 初始化伪装层
    claude_config = ClaudeCodeDisguiseConfig(enabled=settings.claude_disguise_enabled)
    if settings.claude_disguise_user_agent:
        claude_config.user_agent = settings.claude_disguise_user_agent
    if settings.claude_disguise_extra_headers:
        claude_config.extra_headers = settings.claude_disguise_extra_headers
    app.state.claude_disguise = ClaudeCodeDisguise(config=claude_config)
    logger.info(f"Claude disguise: {'enabled' if claude_config.enabled else 'disabled'}")

    openai_config = OpenAIDisguiseConfig(enabled=settings.openai_disguise_enabled)
    if settings.openai_disguise_user_agent:
        openai_config.user_agent = settings.openai_disguise_user_agent
    if settings.openai_disguise_extra_headers:
        openai_config.extra_headers = settings.openai_disguise_extra_headers
    app.state.openai_disguise = OpenAIDisguise(config=openai_config)
    logger.info(f"OpenAI disguise: {'enabled' if openai_config.enabled else 'disabled'}")

    # 可用模型列表
    app.state.available_models = AVAILABLE_MODELS
    logger.info(f"Available models: {len(AVAILABLE_MODELS)}")

    # 确保数据目录存在
    os.makedirs(os.path.dirname(settings.memory_db_path) or ".", exist_ok=True)

    startup_elapsed = time.monotonic() - startup_start
    logger.info(f"Iris AI Gateway ready! (startup took {startup_elapsed:.2f}s)")
    logger.info("=" * 60)

    yield

    # 关闭
    logger.info("Shutting down Iris AI Gateway...")
    if hasattr(app.state, "dispatcher"):
        await app.state.dispatcher.close()
    if hasattr(app.state, "memory_manager") and app.state.memory_manager:
        await app.state.memory_manager.close()
    logger.info("Goodbye!")


# === 创建 FastAPI 应用 ===
app = FastAPI(
    title="Iris AI Gateway",
    description="Unified AI Gateway with dual OpenAI/Anthropic compatibility, persona, memory, and perception",
    version="0.1.0",
    lifespan=lifespan,
)

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === 认证中间件 ===
app.add_middleware(
    AuthMiddleware,
    api_keys=settings.api_key_list,
)

# === 全局异常处理 ===

@app.exception_handler(IrisGatewayError)
async def iris_error_handler(request, exc: IrisGatewayError):
    """统一处理 Iris 自定义异常，不暴露内部细节"""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "code": exc.code,
            }
        },
    )




# === 路由注册 ===
app.include_router(health.router)
app.include_router(openai.router)
app.include_router(anthropic.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.iris_host,
        port=settings.iris_port,
        reload=settings.iris_debug,
        log_level=settings.iris_log_level.lower(),
    )
