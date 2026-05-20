"""Iris AI Gateway - OpenAI 兼容 API 路由

提供 OpenAI Chat Completions API 兼容端点，让 opencode、Cline 等工具直接连入。
通过 CoreProcessor 实现人格注入、记忆增强、感知分析。
"""

import json
import logging

import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from models.openai_schemas import OpenAIChatRequest
from core.protocol_converter import ProtocolConverter
from core.processor import CoreProcessor
from utils.upstream_errors import build_upstream_http_exception

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/chat/completions")
async def openai_chat_completions(
    request: OpenAIChatRequest,
    req: Request,
):
    """OpenAI Chat Completions 兼容端点"""
    processor: CoreProcessor = req.app.state.processor
    converter: ProtocolConverter = req.app.state.converter

    # 获取伪装 headers
    extra_headers = {}
    if hasattr(req.app.state, "openai_disguise"):
        extra_headers = req.app.state.openai_disguise.get_headers()

    # 转换为内部格式
    internal_req = converter.openai_to_internal(request)

    try:
        if request.stream:
            # 流式响应
            return StreamingResponse(
                _openai_stream_generator(processor, converter, internal_req, extra_headers),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            # 非流式响应
            response = await processor.process(internal_req, extra_headers=extra_headers)
            openai_resp = converter.internal_to_openai_response(response)
            return JSONResponse(content=openai_resp.model_dump(exclude_none=True))

    except httpx.HTTPStatusError as e:
        logger.error(f"OpenAI upstream HTTP error: {e.response.status_code} - {e.response.text}")
        raise build_upstream_http_exception(e, "openai")
    except ValueError as e:
        logger.error(f"Provider error: {e}")
        raise HTTPException(status_code=502, detail="Upstream provider error. Please check your configuration.")
    except Exception as e:
        logger.error(f"Request failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error. Please try again later.")


@router.get("/v1/models")
async def openai_list_models(req: Request):
    """OpenAI 模型列表端点"""
    converter: ProtocolConverter = req.app.state.converter
    models = req.app.state.available_models
    response = converter.build_openai_model_list(models)
    return JSONResponse(content=response.model_dump())


@router.post("/v1/completions")
async def openai_completions(request: dict, req: Request):
    """OpenAI Completions 兼容端点（旧版，简单代理）"""
    raise HTTPException(status_code=400, detail="Legacy completions API not supported, please use /v1/chat/completions")


async def _openai_stream_generator(processor, converter, internal_req, extra_headers):
    """OpenAI SSE 流式生成器"""
    try:
        async for chunk in processor.process_stream(internal_req, extra_headers=extra_headers):
            openai_chunk = converter.internal_to_openai_stream_chunk(chunk)
            data = openai_chunk.model_dump(exclude_none=True)
            yield f"data: {json.dumps(data)}\n\n"

        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error(f"Stream error: {e}", exc_info=True)
        error_data = {"error": {"message": str(e), "type": "internal_error"}}
        yield f"data: {json.dumps(error_data)}\n\n"
        yield "data: [DONE]\n\n"
