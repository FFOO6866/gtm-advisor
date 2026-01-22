"""LLM Manager - Central management of LLM providers."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, TypeVar

from pydantic import BaseModel

from .base import LLMProvider, ProviderType, get_provider_for_model
from .openai_provider import OpenAIProvider
from .perplexity_provider import PerplexityProvider

T = TypeVar("T", bound=BaseModel)


class LLMManager:
    """Central manager for LLM providers.

    Handles provider selection, fallback, and routing based on model names.
    """

    def __init__(
        self,
        default_provider: ProviderType | str | None = None,
    ) -> None:
        """Initialize LLM Manager.

        Args:
            default_provider: Default provider to use (from env if not specified)
        """
        if isinstance(default_provider, str):
            default_provider = ProviderType(default_provider)

        self._default_provider = default_provider or ProviderType(
            os.getenv("GTM_DEFAULT_LLM_PROVIDER", "openai")
        )

        # Initialize providers lazily
        self._providers: dict[ProviderType, LLMProvider] = {}

    def _get_provider(self, provider_type: ProviderType) -> LLMProvider:
        """Get or create provider instance.

        Args:
            provider_type: Type of provider

        Returns:
            Provider instance

        Raises:
            ValueError: If provider type is not supported
        """
        if provider_type not in self._providers:
            if provider_type == ProviderType.OPENAI:
                self._providers[provider_type] = OpenAIProvider()
            elif provider_type == ProviderType.PERPLEXITY:
                self._providers[provider_type] = PerplexityProvider()
            elif provider_type == ProviderType.ANTHROPIC:
                # Anthropic provider would be added here
                raise NotImplementedError(
                    "Anthropic provider not yet implemented. Use OpenAI or Perplexity."
                )
            else:
                raise ValueError(f"Unsupported provider: {provider_type}")

        return self._providers[provider_type]

    def get_provider_for_model(self, model: str) -> LLMProvider:
        """Get the appropriate provider for a model.

        Args:
            model: Model name

        Returns:
            Provider instance for the model
        """
        provider_type = get_provider_for_model(model)
        return self._get_provider(provider_type)

    @property
    def default_provider(self) -> LLMProvider:
        """Get the default provider."""
        return self._get_provider(self._default_provider)

    @property
    def openai(self) -> OpenAIProvider:
        """Get OpenAI provider."""
        return self._get_provider(ProviderType.OPENAI)  # type: ignore

    @property
    def perplexity(self) -> PerplexityProvider:
        """Get Perplexity provider for search-augmented responses."""
        return self._get_provider(ProviderType.PERPLEXITY)  # type: ignore

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        provider: ProviderType | str | None = None,
        **kwargs: Any,
    ) -> str:
        """Get completion from appropriate provider.

        Args:
            messages: Chat messages
            model: Model name (determines provider if not specified)
            provider: Explicit provider override
            **kwargs: Additional parameters

        Returns:
            Completion text
        """
        if provider:
            if isinstance(provider, str):
                provider = ProviderType(provider)
            llm = self._get_provider(provider)
        elif model:
            llm = self.get_provider_for_model(model)
        else:
            llm = self.default_provider

        return await llm.complete(messages, model=model, **kwargs)

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
        model: str | None = None,
        provider: ProviderType | str | None = None,
        **kwargs: Any,
    ) -> T:
        """Get structured completion from appropriate provider.

        Args:
            messages: Chat messages
            response_model: Pydantic model for response
            model: Model name (determines provider if not specified)
            provider: Explicit provider override
            **kwargs: Additional parameters

        Returns:
            Structured response
        """
        if provider:
            if isinstance(provider, str):
                provider = ProviderType(provider)
            llm = self._get_provider(provider)
        elif model:
            llm = self.get_provider_for_model(model)
        else:
            llm = self.default_provider

        return await llm.complete_structured(
            messages, response_model, model=model, **kwargs
        )

    async def health_check(self) -> dict[str, bool]:
        """Check health of all configured providers.

        Returns:
            Dict of provider name to health status
        """
        results = {}

        for provider_type in ProviderType:
            try:
                provider = self._get_provider(provider_type)
                if provider.is_configured:
                    results[provider_type.value] = await provider.health_check()
                else:
                    results[provider_type.value] = False
            except (NotImplementedError, ValueError):
                results[provider_type.value] = False

        return results

    def list_configured_providers(self) -> list[str]:
        """List all configured providers.

        Returns:
            List of configured provider names
        """
        configured = []
        for provider_type in ProviderType:
            try:
                provider = self._get_provider(provider_type)
                if provider.is_configured:
                    configured.append(provider_type.value)
            except (NotImplementedError, ValueError):
                pass
        return configured


@lru_cache
def get_llm_manager() -> LLMManager:
    """Get cached LLM manager instance."""
    return LLMManager()
