"""Iris AI Gateway - 健康检查路由"""

import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from config.settings import settings
from models.schemas import HealthResponse

router = APIRouter()
_start_time = time.time()


@router.get("/health")
async def health_check(req: Request):
    """轻量存活检查端点。

    不访问上游 Provider，避免外部网络抖动导致容器被误判为不健康。
    """
    uptime = time.time() - _start_time
    response = HealthResponse(
        version="0.1.0",
        providers={},
        memory_backend=settings.memory_backend,
        uptime=uptime,
    )
    return JSONResponse(content=response.model_dump())


@router.get("/ready")
async def readiness_check(req: Request):
    """就绪检查端点，包含 Provider 和记忆组件状态。"""
    dispatcher = getattr(req.app.state, "dispatcher", None)
    providers_status = {}
    status = "ok"
    if dispatcher:
        try:
            providers_status = await dispatcher.health_check()
        except Exception:
            status = "degraded"
            pass

    if not providers_status or any(not ready for ready in providers_status.values()):
        status = "degraded"

    uptime = time.time() - _start_time
    response = HealthResponse(
        status=status,
        version="0.1.0",
        providers=providers_status,
        memory_backend=settings.memory_backend,
        uptime=uptime,
    )
    return JSONResponse(content=response.model_dump())


@router.get("/")
async def root():
    """根端点"""
    return JSONResponse(content={
        "name": "Iris AI Gateway",
        "version": "0.1.0",
        "description": "Unified AI Gateway with dual OpenAI/Anthropic compatibility",
        "endpoints": {
            "openai": "/v1/chat/completions",
            "anthropic": "/v1/messages",
            "health": "/health",
            "ready": "/ready",
        },
    })
