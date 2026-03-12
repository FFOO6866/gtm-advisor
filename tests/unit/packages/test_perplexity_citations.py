"""Unit tests for PerplexityProvider citation extraction.

These tests verify that complete_with_citations() correctly extracts
citation URLs from both model_extra and direct attributes, and that
research_*_with_citations() convenience wrappers work end-to-end.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.llm.src.perplexity_provider import PerplexityProvider, PerplexityResult


def _make_mock_response(text: str, citations: list[str], use_model_extra: bool = True):
    """Build a mock ChatCompletion-like response."""
    choice = MagicMock()
    choice.message.content = text

    response = MagicMock()
    response.choices = [choice]

    if use_model_extra:
        response.model_extra = {"citations": citations}
        # Ensure direct attribute access falls through to model_extra
        type(response).citations = property(lambda _self: None)
    else:
        response.model_extra = {}
        response.citations = citations

    return response


@pytest.fixture
def provider():
    return PerplexityProvider(api_key="test-key")


class TestCompleteWithCitations:
    @pytest.mark.asyncio
    async def test_extracts_citations_from_model_extra(self, provider):
        """Should extract citations stored in model_extra."""
        urls = ["https://example.com/1", "https://example.com/2"]
        mock_response = _make_mock_response("Research text.", urls, use_model_extra=True)

        with patch.object(provider, "_get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_fn.return_value = mock_client

            result = await provider.complete_with_citations(
                [{"role": "user", "content": "test"}]
            )

        assert isinstance(result, PerplexityResult)
        assert result.text == "Research text."
        assert result.citations == urls

    @pytest.mark.asyncio
    async def test_extracts_citations_from_direct_attribute(self, provider):
        """Should fall back to direct response.citations when model_extra is absent."""
        urls = ["https://source.com/article"]
        mock_response = _make_mock_response("Text.", urls, use_model_extra=False)

        with patch.object(provider, "_get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_fn.return_value = mock_client

            result = await provider.complete_with_citations(
                [{"role": "user", "content": "test"}]
            )

        assert result.citations == urls

    @pytest.mark.asyncio
    async def test_empty_citations_when_none_returned(self, provider):
        """Should return empty list when no citations in response."""
        mock_response = _make_mock_response("Text.", [], use_model_extra=True)

        with patch.object(provider, "_get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_fn.return_value = mock_client

            result = await provider.complete_with_citations(
                [{"role": "user", "content": "test"}]
            )

        assert result.citations == []

    @pytest.mark.asyncio
    async def test_filters_empty_citation_strings(self, provider):
        """Should filter out empty/falsy strings from citations list."""
        urls = ["https://real.com", "", None, "https://another.com"]
        mock_response = _make_mock_response("Text.", urls, use_model_extra=True)

        with patch.object(provider, "_get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_fn.return_value = mock_client

            result = await provider.complete_with_citations(
                [{"role": "user", "content": "test"}]
            )

        assert result.citations == ["https://real.com", "https://another.com"]

    @pytest.mark.asyncio
    async def test_research_market_with_citations_returns_perplexity_result(self, provider):
        """research_market_with_citations() should return a PerplexityResult."""
        urls = ["https://straits-times.com/market"]
        mock_response = _make_mock_response("SaaS market is growing.", urls)

        with patch.object(provider, "_get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_fn.return_value = mock_client

            result = await provider.research_market_with_citations(
                topic="SaaS", region="Singapore"
            )

        assert isinstance(result, PerplexityResult)
        assert result.text == "SaaS market is growing."
        assert result.citations == urls

    @pytest.mark.asyncio
    async def test_research_company_with_citations_returns_perplexity_result(self, provider):
        """research_company_with_citations() should return a PerplexityResult."""
        urls = ["https://linkedin.com/company/acme"]
        mock_response = _make_mock_response("Acme Corp details.", urls)

        with patch.object(provider, "_get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_fn.return_value = mock_client

            result = await provider.research_company_with_citations("Acme Corp")

        assert isinstance(result, PerplexityResult)
        assert result.citations == urls
