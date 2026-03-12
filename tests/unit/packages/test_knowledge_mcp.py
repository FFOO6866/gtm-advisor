"""Unit tests for KnowledgeMCPServer.

Covers:
- Layer 1 framework access (always available, no Qdrant/OpenAI needed)
- Layer 1 fallback when Qdrant is not configured
- search_knowledge falls back to layer1_static when Qdrant unavailable
- query_points API used (not deprecated .search())
- Messaging framework selection logic
- Objection handler routing
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.knowledge.src.knowledge_mcp import KnowledgeMCPServer

# ---------------------------------------------------------------------------
# Layer 1: get_framework
# ---------------------------------------------------------------------------


class TestGetFramework:
    @pytest.mark.asyncio
    async def test_returns_cialdini_principles(self) -> None:
        mcp = KnowledgeMCPServer()
        result = await mcp.get_framework("CIALDINI_PRINCIPLES")
        assert result.get("error") is None
        assert "content" in result
        assert "source_books" in result
        assert isinstance(result["content"], dict)

    @pytest.mark.asyncio
    async def test_returns_error_for_unknown_framework(self) -> None:
        mcp = KnowledgeMCPServer()
        result = await mcp.get_framework("NONEXISTENT_FRAMEWORK")
        assert "error" in result
        assert "available_frameworks" in result

    @pytest.mark.asyncio
    async def test_returns_singapore_sme_context(self) -> None:
        mcp = KnowledgeMCPServer()
        result = await mcp.get_framework("SINGAPORE_SME_CONTEXT")
        assert result.get("error") is None
        content = result["content"]
        assert isinstance(content, dict)


# ---------------------------------------------------------------------------
# Layer 1: get_messaging_framework
# ---------------------------------------------------------------------------


class TestGetMessagingFramework:
    @pytest.mark.asyncio
    async def test_cold_outreach_selects_pas(self) -> None:
        mcp = KnowledgeMCPServer()
        result = await mcp.get_messaging_framework("cold email for Singapore prospects")
        assert result["recommended_framework"] == "PAS"
        assert result["framework_content"]

    @pytest.mark.asyncio
    async def test_case_study_selects_star(self) -> None:
        mcp = KnowledgeMCPServer()
        result = await mcp.get_messaging_framework("writing a case study testimonial")
        assert result["recommended_framework"] == "STAR"

    @pytest.mark.asyncio
    async def test_unknown_use_case_defaults_to_aida(self) -> None:
        mcp = KnowledgeMCPServer()
        result = await mcp.get_messaging_framework("some random task")
        assert result["recommended_framework"] == "AIDA"


# ---------------------------------------------------------------------------
# Layer 1: get_objection_handlers
# ---------------------------------------------------------------------------


class TestGetObjectionHandlers:
    @pytest.mark.asyncio
    async def test_budget_objection_includes_cialdini_scarcity(self) -> None:
        mcp = KnowledgeMCPServer()
        handlers = await mcp.get_objection_handlers("budget too expensive")
        types = [h["type"] for h in handlers]
        assert "cialdini_counter" in types
        # Scarcity and reciprocity are the Cialdini counters for budget
        principles = [h.get("principle") for h in handlers if h["type"] == "cialdini_counter"]
        assert "scarcity" in principles

    @pytest.mark.asyncio
    async def test_trust_objection_includes_authority(self) -> None:
        mcp = KnowledgeMCPServer()
        handlers = await mcp.get_objection_handlers("I don't trust your claims, no proven results")
        principles = [h.get("principle") for h in handlers if h["type"] == "cialdini_counter"]
        assert "authority" in principles

    @pytest.mark.asyncio
    async def test_handlers_contain_universal_sequence(self) -> None:
        mcp = KnowledgeMCPServer()
        handlers = await mcp.get_objection_handlers("timing not right")
        types = [h["type"] for h in handlers]
        assert "universal_sequence" in types


# ---------------------------------------------------------------------------
# Layer 3: search_knowledge — Qdrant unavailable → layer1_static fallback
# ---------------------------------------------------------------------------


class TestSearchKnowledgeFallback:
    @pytest.mark.asyncio
    async def test_falls_back_when_no_qdrant(self) -> None:
        """When Qdrant is not configured, results must have source=layer1_static."""
        mcp = KnowledgeMCPServer(qdrant_url="", openai_api_key="fake-key")
        # Override _get_qdrant to return None (no Qdrant configured)
        mcp._qdrant_path = ""
        mcp._qdrant_url = ""
        results = await mcp.search_knowledge("persuasion techniques cialdini", limit=3)
        # Should fall back to Layer 1
        assert len(results) > 0
        assert all(r.get("source") == "layer1_static" for r in results)

    @pytest.mark.asyncio
    async def test_fallback_returns_relevant_framework(self) -> None:
        mcp = KnowledgeMCPServer(qdrant_url="", openai_api_key="")
        mcp._qdrant_path = ""
        mcp._qdrant_url = ""
        results = await mcp.search_knowledge("porter five forces competitive analysis")
        texts = [r["text"] for r in results]
        assert any("PORTER" in t or "Porter" in t or "five forces" in t.lower() for t in texts)


# ---------------------------------------------------------------------------
# Layer 3: search_knowledge — uses query_points, not deprecated .search()
# ---------------------------------------------------------------------------


class TestSearchKnowledgeQdrantAPI:
    @pytest.mark.asyncio
    async def test_uses_query_points_not_search(self) -> None:
        """Verifies the Qdrant path calls query_points() not the removed .search()."""
        mcp = KnowledgeMCPServer()

        # Mock both clients
        mock_qdrant = AsyncMock()
        mock_openai = AsyncMock()

        # OpenAI returns a fake embedding
        fake_embedding = [0.1] * 1536
        mock_embed_response = MagicMock()
        mock_embed_response.data = [MagicMock(embedding=fake_embedding)]
        mock_openai.embeddings.create = AsyncMock(return_value=mock_embed_response)

        # Qdrant query_points returns a mock response
        mock_hit = MagicMock()
        mock_hit.payload = {
            "book_title": "Test Book",
            "book_key": "test",
            "chapter": "Chapter 1",
            "page_number": 5,
            "text": "This is a test chunk about persuasion.",
            "agent_tags": ["campaign_architect"],
        }
        mock_hit.score = 0.92
        mock_qdrant_response = MagicMock()
        mock_qdrant_response.points = [mock_hit]
        mock_qdrant.query_points = AsyncMock(return_value=mock_qdrant_response)

        # Inject mocked clients
        mcp._qdrant_client = mock_qdrant
        mcp._openai_client = mock_openai

        results = await mcp.search_knowledge("persuasion", limit=1)

        # query_points was called, not search
        mock_qdrant.query_points.assert_called_once()
        assert not hasattr(mock_qdrant, "search") or not mock_qdrant.search.called

        assert len(results) == 1
        assert results[0]["source"] == "qdrant_rag"
        assert results[0]["score"] == 0.92
        assert results[0]["book_title"] == "Test Book"

    @pytest.mark.asyncio
    async def test_agent_filter_applied_when_context_given(self) -> None:
        """Agent context filter is passed as query_filter to query_points."""
        mcp = KnowledgeMCPServer()

        mock_qdrant = AsyncMock()
        mock_openai = AsyncMock()

        fake_embedding = [0.1] * 1536
        mock_embed_response = MagicMock()
        mock_embed_response.data = [MagicMock(embedding=fake_embedding)]
        mock_openai.embeddings.create = AsyncMock(return_value=mock_embed_response)

        mock_qdrant_response = MagicMock()
        mock_qdrant_response.points = []
        mock_qdrant.query_points = AsyncMock(return_value=mock_qdrant_response)

        mcp._qdrant_client = mock_qdrant
        mcp._openai_client = mock_openai

        await mcp.search_knowledge("BANT qualification", agent_context="lead-hunter", limit=5)

        call_kwargs = mock_qdrant.query_points.call_args
        # query_filter should be non-None when agent_context is provided
        assert call_kwargs is not None
        kwargs = call_kwargs.kwargs
        assert kwargs.get("query_filter") is not None

    @pytest.mark.asyncio
    async def test_empty_qdrant_result_falls_back_to_layer1(self) -> None:
        """When query_points returns 0 hits, fall back to Layer 1 results."""
        mcp = KnowledgeMCPServer()

        mock_qdrant = AsyncMock()
        mock_openai = AsyncMock()

        fake_embedding = [0.1] * 1536
        mock_embed_response = MagicMock()
        mock_embed_response.data = [MagicMock(embedding=fake_embedding)]
        mock_openai.embeddings.create = AsyncMock(return_value=mock_embed_response)

        mock_qdrant_response = MagicMock()
        mock_qdrant_response.points = []  # No results
        mock_qdrant.query_points = AsyncMock(return_value=mock_qdrant_response)

        mcp._qdrant_client = mock_qdrant
        mcp._openai_client = mock_openai

        results = await mcp.search_knowledge("cialdini persuasion social proof", limit=3)
        # Falls back to Layer 1
        assert len(results) > 0
        assert all(r.get("source") == "layer1_static" for r in results)


# ---------------------------------------------------------------------------
# Domain guides: get_domain_guide, list_available_guides, get_agent_knowledge_pack
# ---------------------------------------------------------------------------


class TestDomainGuides:
    """Tests for domain guide methods — guides are loaded from JSON files."""

    _SAMPLE_GUIDE = {
        "slug": "digital_awareness_campaign",
        "title": "B2B Digital Awareness Campaign Launch",
        "agent_relevance": ["campaign-architect"],
        "source_books": ["Digital Marketing Strategy", "Ogilvy on Advertising"],
        "source_chunk_count": 12,
        "core_principles": [
            {
                "principle": "Educate before you sell",
                "source": "Scott — New Rules of Marketing",
                "application": "Publish useful content before pitching",
            },
            {
                "principle": "Headline carries 80% of impact",
                "source": "Ogilvy on Advertising",
                "application": "Test 5 headline variants before scaling spend",
            },
        ],
        "process_steps": [
            {
                "step": 1,
                "phase": "Reach",
                "objective": "Build awareness in target accounts",
                "actions": ["LinkedIn thought leadership", "Spotlight ads"],
                "timing": "Weeks 1-4",
            },
            {
                "step": 2,
                "phase": "Act",
                "objective": "Convert engaged visitors",
                "actions": ["Gated content", "PAS copy on gate page"],
                "timing": "Weeks 5-8",
            },
        ],
        "decision_rules": [
            "If audience < 5K: organic LinkedIn first, paid only after 20+ organic followers",
            "If deal > SGD 20K: run ABM targeting named accounts, not broad awareness",
        ],
        "singapore_adaptations": [
            "PSG grant eligibility as conversion hook — halves perceived cost",
            "7+ impression minimum before recognition in Singapore B2B market",
        ],
        "common_mistakes": [
            "Running awareness and conversion campaigns simultaneously",
            "Leading with product features instead of customer problems",
        ],
        "success_metrics": {
            "ICP reach": "60% within 4 weeks",
            "engagement": "3% content rate",
            "pipeline": "15% MQL-to-SQL",
        },
    }

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_domain_guide_returns_none_when_not_found(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Missing guide file returns None gracefully without raising."""
        mcp = KnowledgeMCPServer()
        # Patch the guides dir to an empty temp dir
        import packages.knowledge.src.knowledge_mcp as kmod  # noqa: PLC0415

        original = kmod._GUIDES_DIR
        kmod._GUIDES_DIR = tmp_path
        try:
            result = await mcp.get_domain_guide("nonexistent_guide")
            assert result is None
        finally:
            kmod._GUIDES_DIR = original

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_domain_guide_loads_json_file(self, tmp_path: pytest.TempPathFactory) -> None:
        """Existing guide JSON file is loaded and returned as dict."""
        import packages.knowledge.src.knowledge_mcp as kmod  # noqa: PLC0415

        guide_path = tmp_path / "digital_awareness_campaign.json"
        guide_path.write_text(json.dumps(self._SAMPLE_GUIDE), encoding="utf-8")

        original = kmod._GUIDES_DIR
        kmod._GUIDES_DIR = tmp_path
        try:
            mcp = KnowledgeMCPServer()
            result = await mcp.get_domain_guide("digital_awareness_campaign")
            assert result is not None
            assert result["title"] == "B2B Digital Awareness Campaign Launch"
            assert len(result["core_principles"]) == 2
        finally:
            kmod._GUIDES_DIR = original

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_available_guides_returns_slugs(self, tmp_path: pytest.TempPathFactory) -> None:
        """list_available_guides returns sorted slugs of all .json files."""
        import packages.knowledge.src.knowledge_mcp as kmod  # noqa: PLC0415

        (tmp_path / "cold_email_sequence.json").write_text("{}", encoding="utf-8")
        (tmp_path / "digital_awareness_campaign.json").write_text("{}", encoding="utf-8")

        original = kmod._GUIDES_DIR
        kmod._GUIDES_DIR = tmp_path
        try:
            mcp = KnowledgeMCPServer()
            slugs = await mcp.list_available_guides()
            assert slugs == ["cold_email_sequence", "digital_awareness_campaign"]
        finally:
            kmod._GUIDES_DIR = original

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_available_guides_empty_when_no_dir(self, tmp_path: pytest.TempPathFactory) -> None:
        """list_available_guides returns [] when guides dir does not exist."""
        import packages.knowledge.src.knowledge_mcp as kmod  # noqa: PLC0415

        original = kmod._GUIDES_DIR
        kmod._GUIDES_DIR = tmp_path / "nonexistent"
        try:
            mcp = KnowledgeMCPServer()
            slugs = await mcp.list_available_guides()
            assert slugs == []
        finally:
            kmod._GUIDES_DIR = original

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_agent_knowledge_pack_empty_when_no_guides(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Returns empty pack with empty formatted_injection when no guides exist."""
        import packages.knowledge.src.knowledge_mcp as kmod  # noqa: PLC0415

        original = kmod._GUIDES_DIR
        kmod._GUIDES_DIR = tmp_path  # empty dir, no guide files
        try:
            mcp = KnowledgeMCPServer()
            pack = await mcp.get_agent_knowledge_pack(
                agent_name="campaign-architect",
                task_context="launch an awareness campaign",
            )
            assert pack["guides"] == []
            assert pack["formatted_injection"] == ""
        finally:
            kmod._GUIDES_DIR = original

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_agent_knowledge_pack_loads_relevant_guide(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Loads the most keyword-relevant guide for the task context."""
        import packages.knowledge.src.knowledge_mcp as kmod  # noqa: PLC0415

        (tmp_path / "digital_awareness_campaign.json").write_text(
            json.dumps(self._SAMPLE_GUIDE), encoding="utf-8"
        )
        original = kmod._GUIDES_DIR
        kmod._GUIDES_DIR = tmp_path
        try:
            mcp = KnowledgeMCPServer()
            pack = await mcp.get_agent_knowledge_pack(
                agent_name="campaign-architect",
                task_context="launch a digital awareness campaign for Singapore fintech",
            )
            assert "digital_awareness_campaign" in pack["guides"]
            assert pack["formatted_injection"] != ""
            assert "SYNTHESISED KNOWLEDGE" in pack["formatted_injection"]
        finally:
            kmod._GUIDES_DIR = original

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_agent_knowledge_pack_unknown_agent_returns_empty(self) -> None:
        """Unknown agent name returns empty pack without error."""
        mcp = KnowledgeMCPServer()
        pack = await mcp.get_agent_knowledge_pack(
            agent_name="nonexistent-agent",
            task_context="anything",
        )
        assert pack["guides"] == []
        assert pack["formatted_injection"] == ""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_formatted_injection_respects_token_budget(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Formatted injection stays within the character budget (tokens × 4)."""
        import packages.knowledge.src.knowledge_mcp as kmod  # noqa: PLC0415

        (tmp_path / "digital_awareness_campaign.json").write_text(
            json.dumps(self._SAMPLE_GUIDE), encoding="utf-8"
        )
        original = kmod._GUIDES_DIR
        kmod._GUIDES_DIR = tmp_path
        try:
            mcp = KnowledgeMCPServer()
            pack = await mcp.get_agent_knowledge_pack(
                agent_name="campaign-architect",
                task_context="awareness campaign",
                max_tokens=200,  # tight budget
            )
            injection = pack["formatted_injection"]
            assert len(injection) <= 200 * 4 + 200  # tolerance for header/separator overhead
        finally:
            kmod._GUIDES_DIR = original

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_formatted_injection_contains_key_sections(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Formatted injection block contains all expected section headers."""
        import packages.knowledge.src.knowledge_mcp as kmod  # noqa: PLC0415

        (tmp_path / "digital_awareness_campaign.json").write_text(
            json.dumps(self._SAMPLE_GUIDE), encoding="utf-8"
        )
        original = kmod._GUIDES_DIR
        kmod._GUIDES_DIR = tmp_path
        try:
            mcp = KnowledgeMCPServer()
            pack = await mcp.get_agent_knowledge_pack(
                agent_name="campaign-architect",
                task_context="awareness campaign digital",
                max_tokens=800,
            )
            injection = pack["formatted_injection"]
            assert "CORE PRINCIPLES" in injection
            assert "HOW TO EXECUTE" in injection
            assert "DECISION RULES" in injection
            assert "SINGAPORE" in injection
            assert "AVOID" in injection
            assert "BENCHMARKS" in injection
        finally:
            kmod._GUIDES_DIR = original
