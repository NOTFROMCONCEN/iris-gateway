"""Iris AI Gateway - Anthropic 兼容 API 路由

提供 Anthropic Messages API 兼容端点，让 Claude Code 等工具直接连入。
通过 CoreProcessor 实现人格注入、记忆增强、感知分析。
"""

import json
import logging
import uuid

import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from models.anthropic_schemas import AnthropicMessageRequest
from models.schemas import ProviderType, StreamChunk
from core.protocol_converter import ProtocolConverter
from core.processor import CoreProcessor
from utils.upstream_errors import build_upstream_http_exception

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/messages")
async def anthropic_messages(
    request: AnthropicMessageRequest,
    req: Request,
):
    """Anthropic Messages API 兼容端点"""
    processor: CoreProcessor = req.app.state.processor
    converter: ProtocolConverter = req.app.state.converter

    # 获取伪装 headers
    extra_headers = {}
    if hasattr(req.app.state, "claude_disguise"):
        extra_headers = req.app.state.claude_disguise.get_headers()

    # 转换为内部格式
    internal_req = converter.anthropic_to_internal(request)

    try:
        if request.stream:
            # 流式响应
            msg_id = f"msg_{uuid.uuid4().hex[:24]}"
            return StreamingResponse(
                _anthropic_stream_generator(
                    processor, converter, internal_req,
                    extra_headers, msg_id, request.model,
                ),
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
            anthropic_resp = converter.internal_to_anthropic_response(response)
            return JSONResponse(content=anthropic_resp.model_dump(exclude_none=True))

    except httpx.HTTPStatusError as e:
        logger.error(f"Anthropic upstream HTTP error: {e.response.status_code} - {e.response.text}")
        raise build_upstream_http_exception(e, "anthropic")
    except ValueError as e:
        logger.error(f"Provider error: {e}")
        raise HTTPException(status_code=502, detail="Upstream provider error. Please check your configuration.")
    except Exception as e:
        logger.error(f"Request failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error. Please try again later.")


@router.get("/v1/models")
async def anthropic_list_models(req: Request):
    """Anthropic 模型列表端点"""
    converter: ProtocolConverter = req.app.state.converter
    models = req.app.state.available_models
    # 过滤只返回 Anthropic 模型
    anthropic_models = [
        m for m in models
        if any(kw in m["id"].lower() for kw in ["claude", "anthropic"])
    ]
    response = converter.build_anthropic_model_list(anthropic_models)
    return JSONResponse(content=response.model_dump())


async def _anthropic_stream_generator(
    processor, converter, internal_req, extra_headers, msg_id, model,
):
    """Anthropic SSE 流式生成器"""
    try:
        # 发送 message_start 事件
        start_event = converter.build_anthropic_message_start(model, msg_id)
        yield f"event: {start_event['event']}\ndata: {json.dumps(start_event['data'])}\n\n"

        # 发送 ping
        ping_event = converter.build_anthropic_ping()
        yield f"event: {ping_event['event']}\ndata: {json.dumps(ping_event['data'])}\n\n"

        # 发送 content_block_start
        block_start = converter.build_anthropic_content_block_start()
        yield f"event: {block_start['event']}\ndata: {json.dumps(block_start['data'])}\n\n"

        # 流式内容
        sent_stop = False
        async for chunk in processor.process_stream(internal_req, extra_headers=extra_headers):
            events = converter.internal_to_anthropic_stream_events(chunk)
            for event in events:
                if event["event"] == "message_stop":
                    sent_stop = True
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"

        if not sent_stop:
            events = converter.internal_to_anthropic_stream_events(
                _build_fallback_stop_chunk(msg_id, model)
            )
            for event in events:
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"

    except Exception as e:
        logger.error(f"Anthropic stream error: {e}", exc_info=True)
        error_event = {
            "type": "error",
            "error": {"type": "internal_error", "message": str(e)},
        }
        yield f"event: error\ndata: {json.dumps(error_event)}\n\n"


def _build_fallback_stop_chunk(msg_id: str, model: str) -> StreamChunk:
    """构建缺失上游结束事件时的保底 stop chunk"""
    return StreamChunk(
        id=msg_id,
        delta="",
        provider=ProviderType.ANTHROPIC,
        model=model,
        finish_reason="stop",
    )
