"""Iris AI Gateway - 健康检查路由"""

import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from models.schemas import HealthResponse

router = APIRouter()
_start_time = time.time()


@router.get("/health")
async def health_check(req: Request):
    """健康检查端点"""
    dispatcher = getattr(req.app.state, "dispatcher", None)
    providers_status = {}
    if dispatcher:
        try:
            providers_status = await dispatcher.health_check()
        except Exception:
            pass

    uptime = time.time() - _start_time
    response = HealthResponse(
        version="0.1.0",
        providers=providers_status,
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
        },
    })
