"""Iris AI Gateway - FastAPI 主入口

统一 AI 网关，兼容 OpenAI 和 Anthropic API 协议。
支持人格系统、记忆系统、感知能力，以及上游伪装功能。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from bootstrap import bootstrap, shutdown
from models.exceptions import IrisGatewayError
from middleware import AuthMiddleware
from api import openai, anthropic, health, tools, ui

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    bootstrap(app)
    yield
    await shutdown(app)


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
    allow_origins=settings.cors_origin_list,
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
app.include_router(tools.router)
app.include_router(ui.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.iris_host,
        port=settings.iris_port,
        reload=settings.iris_debug,
        log_level=settings.iris_log_level.lower(),
    )
