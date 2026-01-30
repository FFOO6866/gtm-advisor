"""OpenAI LLM Provider implementation."""

from __future__ import annotations

import os
from typing import Any, TypeVar

from pydantic import BaseModel

from .base import LLMProvider, ProviderType

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider using Instructor for structured outputs."""

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key or os.getenv("OPENAI_API_KEY"))
        self._client = None
        self._instructor_client = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.OPENAI

    @property
    def is_configured(self) -> bool:
        return self._api_key is not None and len(self._api_key) > 0

    @property
    def default_model(self) -> str:
        return "gpt-4o"

    def _get_client(self) -> Any:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self._api_key)
            except ImportError:
                raise ImportError("OpenAI package not installed. Run: pip install openai")
        return self._client

    def _get_instructor_client(self) -> Any:
        """Lazy initialization of Instructor client."""
        if self._instructor_client is None:
            try:
                import instructor

                self._instructor_client = instructor.from_openai(self._get_client())
            except ImportError:
                raise ImportError("Instructor package not installed. Run: pip install instructor")
        return self._instructor_client

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Get completion from OpenAI.

        Args:
            messages: List of chat messages
            model: Model override (default: gpt-4o)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            **kwargs: Additional OpenAI parameters

        Returns:
            Completion text
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
        """Get structured completion using Instructor.

        Args:
            messages: List of chat messages
            response_model: Pydantic model for response validation
            model: Model override (default: gpt-4o)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters

        Returns:
            Structured response matching response_model
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

    async def create_embedding(
        self,
        text: str,
        model: str = "text-embedding-3-small",
    ) -> list[float]:
        """Create embedding for text.

        Args:
            text: Text to embed
            model: Embedding model

        Returns:
            Embedding vector
        """
        client = self._get_client()
        response = await client.embeddings.create(
            model=model,
            input=text,
        )
        return response.data[0].embedding
