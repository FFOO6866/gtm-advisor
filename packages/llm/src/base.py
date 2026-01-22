"""Base LLM Provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ProviderType(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    PERPLEXITY = "perplexity"


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Return provider type."""
        ...

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if provider is properly configured."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return default model for this provider."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Get completion from LLM.

        Args:
            messages: List of chat messages
            model: Model override
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            **kwargs: Additional provider-specific parameters

        Returns:
            Completion text
        """
        ...

    @abstractmethod
    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> T:
        """Get structured completion using Instructor.

        Args:
            messages: List of chat messages
            response_model: Pydantic model for response validation
            model: Model override
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            **kwargs: Additional provider-specific parameters

        Returns:
            Structured response matching response_model
        """
        ...

    async def health_check(self) -> bool:
        """Check if provider is accessible.

        Returns:
            True if healthy
        """
        if not self.is_configured:
            return False
        try:
            await self.complete(
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return True
        except Exception:
            return False


# Model to provider mapping
MODEL_PROVIDER_MAP: dict[str, ProviderType] = {
    # OpenAI models
    "gpt-4o": ProviderType.OPENAI,
    "gpt-4o-mini": ProviderType.OPENAI,
    "gpt-4-turbo": ProviderType.OPENAI,
    "gpt-4": ProviderType.OPENAI,
    "gpt-3.5-turbo": ProviderType.OPENAI,
    "o1": ProviderType.OPENAI,
    "o1-mini": ProviderType.OPENAI,
    # Anthropic models
    "claude-3-5-sonnet-20241022": ProviderType.ANTHROPIC,
    "claude-3-opus-20240229": ProviderType.ANTHROPIC,
    "claude-3-sonnet-20240229": ProviderType.ANTHROPIC,
    "claude-3-haiku-20240307": ProviderType.ANTHROPIC,
    # Perplexity models
    "llama-3.1-sonar-small-128k-online": ProviderType.PERPLEXITY,
    "llama-3.1-sonar-large-128k-online": ProviderType.PERPLEXITY,
    "llama-3.1-sonar-huge-128k-online": ProviderType.PERPLEXITY,
}


def get_provider_for_model(model: str) -> ProviderType:
    """Get the provider type for a given model.

    Args:
        model: Model name

    Returns:
        Provider type for the model

    Raises:
        ValueError: If model is not recognized
    """
    if model in MODEL_PROVIDER_MAP:
        return MODEL_PROVIDER_MAP[model]

    # Try to infer from model name
    model_lower = model.lower()
    if "gpt" in model_lower or "o1" in model_lower:
        return ProviderType.OPENAI
    elif "claude" in model_lower:
        return ProviderType.ANTHROPIC
    elif "sonar" in model_lower or "llama" in model_lower:
        return ProviderType.PERPLEXITY

    raise ValueError(f"Unknown model: {model}")
