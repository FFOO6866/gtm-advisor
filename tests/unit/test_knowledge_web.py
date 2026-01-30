"""Unit tests for Knowledge Web repository and service layer.

These tests verify the database operations for the Knowledge Web
evidence-backed intelligence system.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.knowledge_web import (
    CompetitorSignalRepository,
    EntityRelationRepository,
    EntityRepository,
    EvidencedFactRepository,
    KnowledgeWebService,
    LeadJustificationRepository,
    MCPDataSourceRepository,
)
from packages.database.src.models import (
    EntityType,
    FactType,
    RelationType,
    SourceType,
)


class TestEvidencedFactRepository:
    """Tests for EvidencedFactRepository."""

    @pytest.mark.asyncio
    async def test_create_fact(self, db_session: AsyncSession):
        """Should create and persist an evidenced fact."""
        repo = EvidencedFactRepository(db_session)

        fact = await repo.create(
            claim="Company X raised $10M in Series A funding",
            source_type=SourceType.NEWSAPI,
            fact_type=FactType.FUNDING,
            source_name="TechCrunch",
            source_url="https://techcrunch.com/article/123",
            raw_excerpt="Company X announced today that it has raised...",
            confidence=0.85,
        )

        assert fact.id is not None
        assert fact.claim == "Company X raised $10M in Series A funding"
        assert fact.source_type == SourceType.NEWSAPI
        assert fact.fact_type == FactType.FUNDING
        assert fact.confidence == 0.85
        assert fact.is_verified is False
        assert fact.is_stale is False

    @pytest.mark.asyncio
    async def test_search_facts_by_type(self, db_session: AsyncSession):
        """Should search facts by type."""
        repo = EvidencedFactRepository(db_session)

        # Create facts of different types
        await repo.create(
            claim="Funding news 1",
            source_type=SourceType.NEWSAPI,
            fact_type=FactType.FUNDING,
            source_name="Source1",
            source_url="https://example.com/1",
            confidence=0.8,
        )
        await repo.create(
            claim="Market trend",
            source_type=SourceType.NEWSAPI,
            fact_type=FactType.MARKET_TREND,
            source_name="Source2",
            source_url="https://example.com/2",
            confidence=0.7,
        )

        # Search by type
        funding_facts = await repo.search(fact_type=FactType.FUNDING)
        assert len(funding_facts) == 1
        assert funding_facts[0].claim == "Funding news 1"

    @pytest.mark.asyncio
    async def test_search_facts_by_source(self, db_session: AsyncSession):
        """Should search facts by source type."""
        repo = EvidencedFactRepository(db_session)

        await repo.create(
            claim="News fact",
            source_type=SourceType.NEWSAPI,
            fact_type=FactType.MARKET_TREND,
            source_name="News Source",
            source_url="https://news.com/1",
            confidence=0.8,
        )
        await repo.create(
            claim="Government fact",
            source_type=SourceType.GOVERNMENT,
            fact_type=FactType.MARKET_TREND,
            source_name="Gov Source",
            source_url="https://gov.sg/1",
            confidence=0.9,
        )

        gov_facts = await repo.search(source_type=SourceType.GOVERNMENT)
        assert len(gov_facts) == 1
        assert gov_facts[0].claim == "Government fact"

    @pytest.mark.asyncio
    async def test_mark_stale(self, db_session: AsyncSession):
        """Should mark facts as stale."""
        repo = EvidencedFactRepository(db_session)

        fact = await repo.create(
            claim="Test fact",
            source_type=SourceType.NEWSAPI,
            fact_type=FactType.MARKET_TREND,
            source_name="Source",
            source_url="https://example.com",
            confidence=0.8,
        )

        assert fact.is_stale is False

        await repo.mark_stale(fact.id)
        # Refresh to get updated state
        await db_session.refresh(fact)
        assert fact.is_stale is True

    @pytest.mark.asyncio
    async def test_verify_fact(self, db_session: AsyncSession):
        """Should verify facts."""
        repo = EvidencedFactRepository(db_session)

        fact = await repo.create(
            claim="Test fact",
            source_type=SourceType.NEWSAPI,
            fact_type=FactType.MARKET_TREND,
            source_name="Source",
            source_url="https://example.com",
            confidence=0.8,
        )

        assert fact.is_verified is False

        await repo.verify(fact.id)
        await db_session.refresh(fact)
        assert fact.is_verified is True

    @pytest.mark.asyncio
    async def test_search_with_min_confidence(self, db_session: AsyncSession):
        """Should filter facts by minimum confidence."""
        repo = EvidencedFactRepository(db_session)

        await repo.create(
            claim="Low confidence",
            source_type=SourceType.NEWSAPI,
            fact_type=FactType.MARKET_TREND,
            source_name="Source",
            source_url="https://example.com/1",
            confidence=0.3,
        )
        await repo.create(
            claim="High confidence",
            source_type=SourceType.NEWSAPI,
            fact_type=FactType.MARKET_TREND,
            source_name="Source",
            source_url="https://example.com/2",
            confidence=0.9,
        )

        high_conf_facts = await repo.search(min_confidence=0.7)
        assert len(high_conf_facts) == 1
        assert high_conf_facts[0].claim == "High confidence"


class TestEntityRepository:
    """Tests for EntityRepository."""

    @pytest.mark.asyncio
    async def test_create_entity(self, db_session: AsyncSession):
        """Should create and persist an entity."""
        repo = EntityRepository(db_session)

        entity = await repo.create(
            name="Test Company Pte Ltd",
            entity_type=EntityType.COMPANY,
            acra_uen="202312345A",
            attributes={"industry": "Technology"},
        )

        assert entity.id is not None
        assert entity.name == "Test Company Pte Ltd"
        assert entity.entity_type == EntityType.COMPANY
        assert entity.acra_uen == "202312345A"
        assert entity.attributes["industry"] == "Technology"

    @pytest.mark.asyncio
    async def test_get_by_uen(self, db_session: AsyncSession):
        """Should retrieve entity by UEN."""
        repo = EntityRepository(db_session)

        created = await repo.create(
            name="UEN Test Company",
            entity_type=EntityType.COMPANY,
            acra_uen="202399999Z",
        )

        found = await repo.get_by_uen("202399999Z")
        assert found is not None
        assert found.id == created.id
        assert found.name == "UEN Test Company"

    @pytest.mark.asyncio
    async def test_get_by_uen_not_found(self, db_session: AsyncSession):
        """Should return None for non-existent UEN."""
        repo = EntityRepository(db_session)

        found = await repo.get_by_uen("NONEXISTENT123")
        assert found is None

    @pytest.mark.asyncio
    async def test_find_by_name(self, db_session: AsyncSession):
        """Should find entities by partial name match."""
        repo = EntityRepository(db_session)

        await repo.create(name="Alpha Tech Solutions", entity_type=EntityType.COMPANY)
        await repo.create(name="Beta Tech Industries", entity_type=EntityType.COMPANY)
        await repo.create(name="Gamma Finance", entity_type=EntityType.COMPANY)

        tech_companies = await repo.find_by_name("Tech")
        assert len(tech_companies) == 2

    @pytest.mark.asyncio
    async def test_get_or_create_existing(self, db_session: AsyncSession):
        """Should return existing entity if found."""
        repo = EntityRepository(db_session)

        created = await repo.create(
            name="Existing Company",
            entity_type=EntityType.COMPANY,
            acra_uen="202311111A",
        )

        # Should find existing by UEN
        found, was_created = await repo.get_or_create(
            name="Different Name",  # Name doesn't matter if UEN matches
            entity_type=EntityType.COMPANY,
            acra_uen="202311111A",
        )

        assert was_created is False
        assert found.id == created.id

    @pytest.mark.asyncio
    async def test_get_or_create_new(self, db_session: AsyncSession):
        """Should create new entity if not found."""
        repo = EntityRepository(db_session)

        found, was_created = await repo.get_or_create(
            name="Brand New Company",
            entity_type=EntityType.COMPANY,
            acra_uen="202388888B",
        )

        assert was_created is True
        assert found.name == "Brand New Company"


class TestEntityRelationRepository:
    """Tests for EntityRelationRepository."""

    @pytest.mark.asyncio
    async def test_create_relation(self, db_session: AsyncSession):
        """Should create relation between entities."""
        entity_repo = EntityRepository(db_session)
        relation_repo = EntityRelationRepository(db_session)

        company = await entity_repo.create(
            name="Parent Company",
            entity_type=EntityType.COMPANY,
        )
        partner = await entity_repo.create(
            name="Partner Company",
            entity_type=EntityType.COMPANY,
        )

        relation = await relation_repo.create(
            source_entity_id=company.id,
            target_entity_id=partner.id,
            relation_type=RelationType.PARTNERS_WITH,
            confidence=0.95,
        )

        assert relation.id is not None
        assert relation.source_entity_id == company.id
        assert relation.target_entity_id == partner.id
        assert relation.relation_type == RelationType.PARTNERS_WITH

    @pytest.mark.asyncio
    async def test_get_relations(self, db_session: AsyncSession):
        """Should get all relations for an entity."""
        entity_repo = EntityRepository(db_session)
        relation_repo = EntityRelationRepository(db_session)

        company = await entity_repo.create(
            name="Main Company",
            entity_type=EntityType.COMPANY,
        )
        partner1 = await entity_repo.create(
            name="Partner 1",
            entity_type=EntityType.COMPANY,
        )
        partner2 = await entity_repo.create(
            name="Partner 2",
            entity_type=EntityType.COMPANY,
        )

        await relation_repo.create(
            source_entity_id=company.id,
            target_entity_id=partner1.id,
            relation_type=RelationType.PARTNERS_WITH,
            confidence=0.8,
        )
        await relation_repo.create(
            source_entity_id=company.id,
            target_entity_id=partner2.id,
            relation_type=RelationType.PARTNERS_WITH,
            confidence=0.7,
        )

        relations = await relation_repo.get_relations(company.id)
        assert len(relations) == 2

    @pytest.mark.asyncio
    async def test_end_relation(self, db_session: AsyncSession):
        """Should end a relation by setting valid_until."""
        entity_repo = EntityRepository(db_session)
        relation_repo = EntityRelationRepository(db_session)

        company = await entity_repo.create(
            name="Company A",
            entity_type=EntityType.COMPANY,
        )
        partner = await entity_repo.create(
            name="Company B",
            entity_type=EntityType.COMPANY,
        )

        relation = await relation_repo.create(
            source_entity_id=company.id,
            target_entity_id=partner.id,
            relation_type=RelationType.PARTNERS_WITH,
            confidence=0.8,
        )

        assert relation.is_current is True

        await relation_repo.end_relation(relation.id)
        await db_session.refresh(relation)
        assert relation.is_current is False
        assert relation.valid_until is not None


class TestLeadJustificationRepository:
    """Tests for LeadJustificationRepository."""

    @pytest.mark.asyncio
    async def test_create_justification(self, db_session: AsyncSession):
        """Should create lead justification with linked facts."""
        fact_repo = EvidencedFactRepository(db_session)
        just_repo = LeadJustificationRepository(db_session)

        # Create supporting facts
        fact1 = await fact_repo.create(
            claim="Company is expanding to Singapore",
            source_type=SourceType.NEWSAPI,
            fact_type=FactType.EXPANSION,
            source_name="BizNews",
            source_url="https://biznews.com/1",
            confidence=0.9,
        )
        fact2 = await fact_repo.create(
            claim="Company hiring 50 engineers",
            source_type=SourceType.WEB_SCRAPE,
            fact_type=FactType.HIRING,
            source_name="LinkedIn",
            source_url="https://linkedin.com/jobs/123",
            confidence=0.85,
        )

        lead_id = uuid4()
        justification = await just_repo.create(
            lead_id=lead_id,
            signal_category="expansion",
            signal_type="market_entry",
            signal_description="Company shows strong expansion signals with Singapore market entry",
            evidence_fact_ids=[fact1.id, fact2.id],
            impact_score=0.87,
        )

        assert justification.id is not None
        assert justification.lead_id == lead_id
        assert justification.signal_category == "expansion"
        assert justification.impact_score == 0.87

    @pytest.mark.asyncio
    async def test_get_justifications_for_lead(self, db_session: AsyncSession):
        """Should get all justifications for a lead."""
        just_repo = LeadJustificationRepository(db_session)

        lead_id = uuid4()

        await just_repo.create(
            lead_id=lead_id,
            signal_category="funding",
            signal_type="series_a",
            signal_description="Recent funding round",
            evidence_fact_ids=[],
            impact_score=0.8,
        )
        await just_repo.create(
            lead_id=lead_id,
            signal_category="growth",
            signal_type="headcount",
            signal_description="Rapid headcount growth",
            evidence_fact_ids=[],
            impact_score=0.7,
        )

        justifications = await just_repo.get_for_lead(lead_id)
        assert len(justifications) == 2


class TestCompetitorSignalRepository:
    """Tests for CompetitorSignalRepository."""

    @pytest.mark.asyncio
    async def test_create_signal(self, db_session: AsyncSession):
        """Should create competitor signal."""
        fact_repo = EvidencedFactRepository(db_session)
        signal_repo = CompetitorSignalRepository(db_session)

        fact = await fact_repo.create(
            claim="Competitor launched new product",
            source_type=SourceType.NEWSAPI,
            fact_type=FactType.PRODUCT,
            source_name="TechNews",
            source_url="https://technews.com/1",
            confidence=0.9,
        )

        competitor_id = uuid4()
        signal = await signal_repo.create(
            competitor_id=competitor_id,
            signal_type="product_launch",
            severity="medium",
            title="Competitor launched a competing product",
            primary_fact_id=fact.id,
        )

        assert signal.id is not None
        assert signal.competitor_id == competitor_id
        assert signal.signal_type == "product_launch"
        assert signal.severity == "medium"
        assert signal.is_acknowledged is False

    @pytest.mark.asyncio
    async def test_acknowledge_signal(self, db_session: AsyncSession):
        """Should acknowledge a signal."""
        signal_repo = CompetitorSignalRepository(db_session)

        competitor_id = uuid4()
        signal = await signal_repo.create(
            competitor_id=competitor_id,
            signal_type="price_change",
            severity="low",
            title="Minor price adjustment",
        )

        assert signal.is_acknowledged is False

        await signal_repo.acknowledge(signal.id)
        await db_session.refresh(signal)
        assert signal.is_acknowledged is True
        assert signal.acknowledged_at is not None


class TestMCPDataSourceRepository:
    """Tests for MCPDataSourceRepository."""

    @pytest.mark.asyncio
    async def test_register_data_source(self, db_session: AsyncSession):
        """Should register an MCP data source."""
        repo = MCPDataSourceRepository(db_session)

        source = await repo.register(
            name="acra",
            source_type=SourceType.GOVERNMENT,
            description="ACRA Singapore",
            endpoint_url="https://data.gov.sg",
            rate_limit_per_hour=60,
        )

        assert source.id is not None
        assert source.name == "acra"
        assert source.source_type == SourceType.GOVERNMENT
        assert source.is_enabled is True

    @pytest.mark.asyncio
    async def test_get_enabled_sources(self, db_session: AsyncSession):
        """Should get all enabled data sources."""
        repo = MCPDataSourceRepository(db_session)

        await repo.register(
            name="source1",
            source_type=SourceType.NEWSAPI,
            description="Source 1",
        )
        source2 = await repo.register(
            name="source2",
            source_type=SourceType.NEWSAPI,
            description="Source 2",
        )

        # Disable source2
        source2.is_enabled = False
        db_session.add(source2)
        await db_session.commit()

        enabled = await repo.get_all_enabled()
        assert len(enabled) == 1
        assert enabled[0].name == "source1"

    @pytest.mark.asyncio
    async def test_update_health(self, db_session: AsyncSession):
        """Should update source health status."""
        repo = MCPDataSourceRepository(db_session)

        source = await repo.register(
            name="test_source",
            source_type=SourceType.NEWSAPI,
            description="Test Source",
        )

        # Update to unhealthy
        await repo.update_health("test_source", is_healthy=False)
        await db_session.refresh(source)

        assert source.is_healthy is False

    @pytest.mark.asyncio
    async def test_record_sync(self, db_session: AsyncSession):
        """Should record successful sync."""
        repo = MCPDataSourceRepository(db_session)

        source = await repo.register(
            name="sync_source",
            source_type=SourceType.NEWSAPI,
            description="Sync Source",
        )

        assert source.last_sync is None

        await repo.record_sync("sync_source", facts_produced=25, avg_confidence=0.85)
        await db_session.refresh(source)

        assert source.last_sync is not None
        assert source.total_facts_produced == 25


class TestKnowledgeWebService:
    """Tests for KnowledgeWebService orchestration."""

    @pytest.mark.asyncio
    async def test_service_initialization(self, db_session: AsyncSession):
        """Should initialize with all repositories."""
        service = KnowledgeWebService(db_session)

        assert service.facts is not None
        assert service.entities is not None
        assert service.relations is not None
        assert service.justifications is not None
        assert service.competitor_signals is not None
        assert service.data_sources is not None
