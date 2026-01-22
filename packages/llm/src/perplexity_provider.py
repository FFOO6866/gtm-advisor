"""Perplexity LLM Provider implementation.

Perplexity provides search-augmented LLM responses, ideal for market research
and real-time information retrieval.
"""

from __future__ import annotations

import os
from typing import Any, TypeVar

from pydantic import BaseModel

from .base import LLMProvider, ProviderType

T = TypeVar("T", bound=BaseModel)


class PerplexityProvider(LLMProvider):
    """Perplexity LLM provider for search-augmented responses.

    Perplexity uses an OpenAI-compatible API, so we use the OpenAI client
    with a different base URL.
    """

    PERPLEXITY_BASE_URL = "https://api.perplexity.ai"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key or os.getenv("PERPLEXITY_API_KEY"))
        self._client = None
        self._instructor_client = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.PERPLEXITY

    @property
    def is_configured(self) -> bool:
        return self._api_key is not None and len(self._api_key) > 0

    @property
    def default_model(self) -> str:
        return "llama-3.1-sonar-large-128k-online"

    def _get_client(self) -> Any:
        """Lazy initialization of Perplexity client (OpenAI-compatible)."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    api_key=self._api_key,
                    base_url=self.PERPLEXITY_BASE_URL,
                )
            except ImportError:
                raise ImportError(
                    "OpenAI package not installed. Run: pip install openai"
                )
        return self._client

    def _get_instructor_client(self) -> Any:
        """Lazy initialization of Instructor client for Perplexity."""
        if self._instructor_client is None:
            try:
                import instructor

                self._instructor_client = instructor.from_openai(self._get_client())
            except ImportError:
                raise ImportError(
                    "Instructor package not installed. Run: pip install instructor"
                )
        return self._instructor_client

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Get search-augmented completion from Perplexity.

        Args:
            messages: List of chat messages
            model: Model override (default: llama-3.1-sonar-large-128k-online)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters

        Returns:
            Completion text with real-time search results
        """
        client = self._get_client()

        params: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            params["max_tokens"] = max_tokens
        params.update(kwargs)

        response = await client.chat.completions.create(**params)
        return response.choices[0].message.content or ""

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> T:
        """Get structured search-augmented completion.

        Args:
            messages: List of chat messages
            response_model: Pydantic model for response validation
            model: Model override
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters

        Returns:
            Structured response with search-augmented data
        """
        client = self._get_instructor_client()

        params: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "response_model": response_model,
            "temperature": temperature,
        }
        if max_tokens:
            params["max_tokens"] = max_tokens
        params.update(kwargs)

        return await client.chat.completions.create(**params)

    async def search(
        self,
        query: str,
        focus: str = "internet",
        **kwargs: Any,
    ) -> str:
        """Perform search-augmented query.

        This is a convenience method for research tasks.

        Args:
            query: Search query
            focus: Search focus (internet, academic, news, etc.)
            **kwargs: Additional parameters

        Returns:
            Search-augmented response
        """
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a research assistant focused on {focus} searches. "
                    "Provide comprehensive, factual information with sources."
                ),
            },
            {"role": "user", "content": query},
        ]

        return await self.complete(messages, **kwargs)

    async def research_market(
        self,
        topic: str,
        region: str = "Singapore",
        **kwargs: Any,
    ) -> str:
        """Research market information.

        Args:
            topic: Market topic to research
            region: Geographic focus
            **kwargs: Additional parameters

        Returns:
            Market research response
        """
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a market research analyst specializing in {region}. "
                    "Provide detailed market insights, trends, and data with sources. "
                    "Focus on actionable insights for businesses."
                ),
            },
            {
                "role": "user",
                "content": f"Research the following market topic: {topic}",
            },
        ]

        return await self.complete(messages, **kwargs)

    async def research_company(
        self,
        company_name: str,
        **kwargs: Any,
    ) -> str:
        """Research company information.

        Args:
            company_name: Company to research
            **kwargs: Additional parameters

        Returns:
            Company research response
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a business intelligence analyst. "
                    "Provide detailed company information including: "
                    "founding date, headquarters, products/services, "
                    "key executives, funding, recent news, and competitive position. "
                    "Include sources for all information."
                ),
            },
            {
                "role": "user",
                "content": f"Research the company: {company_name}",
            },
        ]

        return await self.complete(messages, **kwargs)
