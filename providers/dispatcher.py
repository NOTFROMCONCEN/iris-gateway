"""Iris AI Gateway - Provider 调度器

根据请求的 provider 类型选择对应的上游 Provider，并应用伪装配置。
支持请求追踪（request_id + 耗时统计）。
"""

import asyncio
import logging
import time
from typing import AsyncIterator, Optional, Dict, Any, List

from models.schemas import ChatRequest, ChatResponse, StreamChunk, ProviderType
from providers.base import BaseProvider
from providers.anthropic_provider import AnthropicProvider
from providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class ProviderDispatcher:
    """Provider 调度器 - 路由请求到正确的上游 Provider"""

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        anthropic_base_url: Optional[str] = None,
        anthropic_auth_header: str = "x-api-key",
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
        openai_organization: Optional[str] = None,
        timeout: int = 120,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self._providers: Dict[ProviderType, BaseProvider] = {}
        self._timeout = timeout

        # 初始化 Anthropic Provider
        if anthropic_api_key:
            self._providers[ProviderType.ANTHROPIC] = AnthropicProvider(
                api_key=anthropic_api_key,
                base_url=anthropic_base_url,
                timeout=timeout,
                auth_header=anthropic_auth_header,
                max_retries=max_retries,
                retry_delay=retry_delay,
            )
            logger.info(f"Anthropic provider initialized (auth_header={anthropic_auth_header})")

        # 初始化 OpenAI Provider
        if openai_api_key:
            self._providers[ProviderType.OPENAI] = OpenAIProvider(
                api_key=openai_api_key,
                base_url=openai_base_url,
                timeout=timeout,
                organization=openai_organization,
                max_retries=max_retries,
                retry_delay=retry_delay,
            )
            logger.info("OpenAI provider initialized")

    def get_provider(self, provider_type: ProviderType) -> Optional[BaseProvider]:
        """获取指定类型的 Provider"""
        return self._providers.get(provider_type)

    def has_provider(self, provider_type: ProviderType) -> bool:
        """检查是否有指定类型的 Provider"""
        return provider_type in self._providers

    async def dispatch(
        self,
        request: ChatRequest,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> ChatResponse:
        """非流式调度请求到上游 Provider（带耗时统计）"""
        provider_type = request.provider or ProviderType.OPENAI
        provider = self._providers.get(provider_type)

        if not provider:
            raise ValueError(f"Provider {provider_type.value} not configured")

        request_id = request.metadata.get("request_id", "unknown")
        logger.info(
            f"[{request_id}] Dispatching to {provider_type.value} "
            f"(model={request.model}, stream=False)"
        )

        start_time = time.monotonic()
        try:
            response = await provider.chat(request, extra_headers=extra_headers)
            elapsed = time.monotonic() - start_time
            logger.info(
                f"[{request_id}] Completed in {elapsed:.2f}s "
                f"(model={request.model}, tokens={response.usage})"
            )
            return response
        except Exception as e:
            elapsed = time.monotonic() - start_time
            logger.error(
                f"[{request_id}] Failed after {elapsed:.2f}s "
                f"(model={request.model}): {e}"
            )
            raise

    async def dispatch_stream(
        self,
        request: ChatRequest,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> AsyncIterator[StreamChunk]:
        """流式调度请求到上游 Provider（带耗时统计）"""
        provider_type = request.provider or ProviderType.OPENAI
        provider = self._providers.get(provider_type)

        if not provider:
            raise ValueError(f"Provider {provider_type.value} not configured")

        request_id = request.metadata.get("request_id", "unknown")
        logger.info(
            f"[{request_id}] Dispatching stream to {provider_type.value} "
            f"(model={request.model})"
        )

        start_time = time.monotonic()
        chunk_count = 0
        try:
            async for chunk in provider.chat_stream(request, extra_headers=extra_headers):
                chunk_count += 1
                yield chunk
            elapsed = time.monotonic() - start_time
            logger.info(
                f"[{request_id}] Stream completed in {elapsed:.2f}s "
                f"({chunk_count} chunks)"
            )
        except Exception as e:
            elapsed = time.monotonic() - start_time
            logger.error(
                f"[{request_id}] Stream failed after {elapsed:.2f}s "
                f"({chunk_count} chunks): {e}"
            )
            raise

    async def health_check(self) -> Dict[str, bool]:
        """检查所有 Provider 的健康状态"""
        results = {}
        for ptype, provider in self._providers.items():
            try:
                results[ptype.value] = await provider.health_check()
            except Exception:
                results[ptype.value] = False
        return results

    async def list_all_models(self) -> List[Dict[str, Any]]:
        """聚合所有已配置上游 Provider 的模型列表

        并行调用每个 Provider 的 list_models，去重后合并返回。
        """
        tasks = []
        provider_names = []
        for ptype, provider in self._providers.items():
            tasks.append(provider.list_models())
            provider_names.append(ptype.value)

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        seen = set()
        models = []
        for name, result in zip(provider_names, results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to list models from {name}: {result}")
                continue
            for m in result:
                model_id = m.get("id")
                if not model_id or model_id in seen:
                    continue
                seen.add(model_id)
                # 标记来源
                m["owned_by"] = f"{name}/{m.get('owned_by', 'unknown')}"
                models.append(m)

        logger.info(f"Discovered {len(models)} models from {len(self._providers)} provider(s)")
        return models

    async def close(self):
        """关闭所有 Provider"""
        for provider in self._providers.values():
            await provider.close()
