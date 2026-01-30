"""Knowledge Web Repository and Service Layer.

Provides CRUD operations and business logic for the Knowledge Web:
- EvidencedFact storage and retrieval
- Entity management and deduplication
- Relationship tracking
- Lead justification management
- Competitor signal tracking

All operations use async SQLAlchemy sessions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.database.src.models import (
    CompetitorSignal,
    Entity,
    EntityRelation,
    EntityType,
    EvidencedFact,
    FactEntityLink,
    FactType,
    LeadJustification,
    MCPDataSource,
    RelationType,
    SourceType,
)


class EvidencedFactRepository:
    """Repository for EvidencedFact CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        claim: str,
        fact_type: FactType,
        source_type: SourceType,
        source_name: str,
        source_url: str | None = None,
        raw_excerpt: str | None = None,
        published_at: datetime | None = None,
        confidence: float = 0.8,
        extracted_data: dict[str, Any] | None = None,
        mcp_server: str | None = None,
        related_entity_ids: list[UUID] | None = None,
    ) -> EvidencedFact:
        """Create a new evidenced fact.

        Args:
            claim: The factual claim
            fact_type: Type of fact
            source_type: Type of source
            source_name: Name of source
            source_url: URL to source
            raw_excerpt: Original text excerpt
            published_at: When source was published
            confidence: Confidence score (0-1)
            extracted_data: Structured data from fact
            mcp_server: MCP server that produced this
            related_entity_ids: UUIDs of related entities

        Returns:
            Created fact
        """
        fact = EvidencedFact(
            claim=claim,
            fact_type=fact_type,
            source_type=source_type,
            source_name=source_name,
            source_url=source_url,
            raw_excerpt=raw_excerpt,
            published_at=published_at,
            confidence=confidence,
            extracted_data=extracted_data or {},
            mcp_server=mcp_server,
        )
        self._session.add(fact)
        await self._session.flush()

        # Link to entities
        if related_entity_ids:
            for entity_id in related_entity_ids:
                link = FactEntityLink(
                    fact_id=fact.id,
                    entity_id=entity_id,
                    role="subject",
                )
                self._session.add(link)

        await self._session.commit()
        await self._session.refresh(fact)
        return fact

    async def create_from_mcp_fact(
        self,
        mcp_fact: Any,  # EvidencedFact from MCP types
    ) -> EvidencedFact:
        """Create from an MCP EvidencedFact type.

        Args:
            mcp_fact: EvidencedFact from packages.mcp.src.types

        Returns:
            Database model instance
        """
        return await self.create(
            claim=mcp_fact.claim,
            fact_type=FactType(mcp_fact.fact_type.value),
            source_type=SourceType(mcp_fact.source_type.value),
            source_name=mcp_fact.source_name,
            source_url=mcp_fact.source_url,
            raw_excerpt=mcp_fact.raw_excerpt,
            published_at=mcp_fact.published_at,
            confidence=mcp_fact.confidence,
            extracted_data=mcp_fact.extracted_data,
            mcp_server=mcp_fact.mcp_server,
        )

    async def get_by_id(self, fact_id: UUID) -> EvidencedFact | None:
        """Get fact by ID."""
        result = await self._session.execute(
            select(EvidencedFact)
            .options(selectinload(EvidencedFact.entity_links))
            .where(EvidencedFact.id == fact_id)
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        query: str | None = None,
        fact_type: FactType | None = None,
        source_type: SourceType | None = None,
        min_confidence: float = 0.0,
        entity_id: UUID | None = None,
        since: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EvidencedFact]:
        """Search facts with filters.

        Args:
            query: Text search in claim
            fact_type: Filter by fact type
            source_type: Filter by source type
            min_confidence: Minimum confidence threshold
            entity_id: Filter by related entity
            since: Only facts captured after this time
            limit: Max results
            offset: Pagination offset

        Returns:
            List of matching facts
        """
        stmt = select(EvidencedFact).options(
            selectinload(EvidencedFact.entity_links)
        )

        conditions = []

        if query:
            conditions.append(EvidencedFact.claim.ilike(f"%{query}%"))

        if fact_type:
            conditions.append(EvidencedFact.fact_type == fact_type)

        if source_type:
            conditions.append(EvidencedFact.source_type == source_type)

        if min_confidence > 0:
            conditions.append(EvidencedFact.confidence >= min_confidence)

        if since:
            conditions.append(EvidencedFact.captured_at >= since)

        if entity_id:
            stmt = stmt.join(FactEntityLink).where(
                FactEntityLink.entity_id == entity_id
            )

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = (
            stmt.order_by(EvidencedFact.captured_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_source(
        self,
        source_type: SourceType,
        source_url: str | None = None,
        limit: int = 100,
    ) -> list[EvidencedFact]:
        """Get facts from a specific source."""
        stmt = select(EvidencedFact).where(
            EvidencedFact.source_type == source_type
        )

        if source_url:
            stmt = stmt.where(EvidencedFact.source_url == source_url)

        stmt = stmt.order_by(EvidencedFact.captured_at.desc()).limit(limit)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_stale(self, fact_id: UUID) -> None:
        """Mark a fact as stale."""
        fact = await self.get_by_id(fact_id)
        if fact:
            fact.is_stale = True
            await self._session.commit()

    async def verify(self, fact_id: UUID) -> None:
        """Mark a fact as verified."""
        fact = await self.get_by_id(fact_id)
        if fact:
            fact.is_verified = True
            await self._session.commit()

    async def increment_verification(self, fact_id: UUID) -> None:
        """Increment verification count (cross-source confirmation)."""
        fact = await self.get_by_id(fact_id)
        if fact:
            fact.verification_count += 1
            # Boost confidence slightly for multiple sources
            fact.confidence = min(1.0, fact.confidence + 0.05)
            await self._session.commit()

    async def find_similar(
        self,
        claim: str,
        threshold: float = 0.8,
    ) -> list[EvidencedFact]:
        """Find facts with similar claims (for deduplication)."""
        # Simple approach: search for key words
        # In production, use vector similarity search
        words = claim.lower().split()[:5]  # First 5 words
        conditions = [
            EvidencedFact.claim.ilike(f"%{word}%")
            for word in words
            if len(word) > 3
        ]

        if not conditions:
            return []

        stmt = (
            select(EvidencedFact)
            .where(or_(*conditions))
            .where(EvidencedFact.confidence >= threshold)
            .limit(10)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class EntityRepository:
    """Repository for Entity CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        entity_type: EntityType,
        name: str,
        canonical_name: str | None = None,
        acra_uen: str | None = None,
        website: str | None = None,
        linkedin_url: str | None = None,
        description: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Entity:
        """Create a new entity."""
        entity = Entity(
            entity_type=entity_type,
            name=name,
            canonical_name=canonical_name or name.upper(),
            acra_uen=acra_uen,
            website=website,
            linkedin_url=linkedin_url,
            description=description,
            attributes=attributes or {},
        )
        self._session.add(entity)
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def get_by_id(self, entity_id: UUID) -> Entity | None:
        """Get entity by ID."""
        result = await self._session.execute(
            select(Entity)
            .options(
                selectinload(Entity.fact_links),
                selectinload(Entity.outgoing_relations),
                selectinload(Entity.incoming_relations),
            )
            .where(Entity.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def get_by_uen(self, uen: str) -> Entity | None:
        """Get entity by ACRA UEN."""
        result = await self._session.execute(
            select(Entity).where(Entity.acra_uen == uen)
        )
        return result.scalar_one_or_none()

    async def find_by_name(
        self,
        name: str,
        entity_type: EntityType | None = None,
    ) -> list[Entity]:
        """Find entities by name (case-insensitive)."""
        stmt = select(Entity).where(
            or_(
                Entity.name.ilike(f"%{name}%"),
                Entity.canonical_name.ilike(f"%{name}%"),
            )
        )

        if entity_type:
            stmt = stmt.where(Entity.entity_type == entity_type)

        stmt = stmt.limit(20)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_or_create(
        self,
        entity_type: EntityType,
        name: str,
        **kwargs: Any,
    ) -> tuple[Entity, bool]:
        """Get existing entity or create new one.

        Returns:
            Tuple of (entity, created) where created is True if new
        """
        # Try to find by UEN first if provided
        uen = kwargs.get("acra_uen")
        if uen:
            existing = await self.get_by_uen(uen)
            if existing:
                return existing, False

        # Try to find by canonical name
        canonical = name.upper()
        result = await self._session.execute(
            select(Entity).where(
                and_(
                    Entity.entity_type == entity_type,
                    Entity.canonical_name == canonical,
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            return existing, False

        # Create new
        entity = await self.create(
            entity_type=entity_type,
            name=name,
            canonical_name=canonical,
            **kwargs,
        )
        return entity, True

    async def update_fact_count(self, entity_id: UUID) -> None:
        """Update the fact_count for an entity."""
        result = await self._session.execute(
            select(func.count(FactEntityLink.id)).where(
                FactEntityLink.entity_id == entity_id
            )
        )
        count = result.scalar() or 0

        entity = await self.get_by_id(entity_id)
        if entity:
            entity.fact_count = count
            entity.last_updated = datetime.utcnow()
            await self._session.commit()

    async def merge_entities(
        self,
        source_id: UUID,
        target_id: UUID,
    ) -> Entity:
        """Merge source entity into target entity.

        All relationships and facts are transferred to target.
        Source is marked as merged.
        """
        source = await self.get_by_id(source_id)
        target = await self.get_by_id(target_id)

        if not source or not target:
            raise ValueError("Source or target entity not found")

        # Transfer fact links
        await self._session.execute(
            FactEntityLink.__table__.update()
            .where(FactEntityLink.entity_id == source_id)
            .values(entity_id=target_id)
        )

        # Transfer outgoing relations
        await self._session.execute(
            EntityRelation.__table__.update()
            .where(EntityRelation.source_entity_id == source_id)
            .values(source_entity_id=target_id)
        )

        # Transfer incoming relations
        await self._session.execute(
            EntityRelation.__table__.update()
            .where(EntityRelation.target_entity_id == source_id)
            .values(target_entity_id=target_id)
        )

        # Mark source as merged
        source.is_active = False
        source.merged_into_id = target_id

        # Update target fact count
        await self.update_fact_count(target_id)

        await self._session.commit()
        await self._session.refresh(target)

        return target


class EntityRelationRepository:
    """Repository for EntityRelation CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        source_entity_id: UUID,
        target_entity_id: UUID,
        relation_type: RelationType,
        attributes: dict[str, Any] | None = None,
        confidence: float = 0.8,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
    ) -> EntityRelation:
        """Create a relationship between entities."""
        relation = EntityRelation(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relation_type=relation_type,
            attributes=attributes or {},
            confidence=confidence,
            valid_from=valid_from,
            valid_until=valid_until,
            is_current=valid_until is None,
        )
        self._session.add(relation)
        await self._session.commit()
        await self._session.refresh(relation)
        return relation

    async def get_relations(
        self,
        entity_id: UUID,
        relation_type: RelationType | None = None,
        direction: str = "both",  # "outgoing", "incoming", or "both"
    ) -> list[EntityRelation]:
        """Get relations for an entity."""
        conditions = []

        if direction in ("outgoing", "both"):
            conditions.append(EntityRelation.source_entity_id == entity_id)
        if direction in ("incoming", "both"):
            conditions.append(EntityRelation.target_entity_id == entity_id)

        stmt = select(EntityRelation).where(or_(*conditions))

        if relation_type:
            stmt = stmt.where(EntityRelation.relation_type == relation_type)

        stmt = stmt.where(EntityRelation.is_current == True)  # noqa: E712

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_existing(
        self,
        source_id: UUID,
        target_id: UUID,
        relation_type: RelationType,
    ) -> EntityRelation | None:
        """Find existing relation between entities."""
        result = await self._session.execute(
            select(EntityRelation).where(
                and_(
                    EntityRelation.source_entity_id == source_id,
                    EntityRelation.target_entity_id == target_id,
                    EntityRelation.relation_type == relation_type,
                    EntityRelation.is_current == True,  # noqa: E712
                )
            )
        )
        return result.scalar_one_or_none()

    async def end_relation(
        self,
        relation_id: UUID,
        end_date: datetime | None = None,
    ) -> None:
        """Mark a relation as no longer current."""
        result = await self._session.execute(
            select(EntityRelation).where(EntityRelation.id == relation_id)
        )
        relation = result.scalar_one_or_none()

        if relation:
            relation.is_current = False
            relation.valid_until = end_date or datetime.utcnow()
            await self._session.commit()


class LeadJustificationRepository:
    """Repository for LeadJustification CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        lead_id: UUID,
        signal_category: str,
        signal_type: str,
        signal_description: str,
        impact_score: float = 0.5,
        evidence_fact_ids: list[UUID] | None = None,
        evidence_summary: str | None = None,
    ) -> LeadJustification:
        """Create a lead justification."""
        justification = LeadJustification(
            lead_id=lead_id,
            signal_category=signal_category,
            signal_type=signal_type,
            signal_description=signal_description,
            impact_score=impact_score,
            evidence_fact_ids=[str(fid) for fid in (evidence_fact_ids or [])],
            evidence_summary=evidence_summary,
        )
        self._session.add(justification)
        await self._session.commit()
        await self._session.refresh(justification)
        return justification

    async def get_for_lead(self, lead_id: UUID) -> list[LeadJustification]:
        """Get all justifications for a lead."""
        result = await self._session.execute(
            select(LeadJustification)
            .where(LeadJustification.lead_id == lead_id)
            .order_by(LeadJustification.impact_score.desc())
        )
        return list(result.scalars().all())

    async def get_by_category(
        self,
        lead_id: UUID,
        category: str,
    ) -> list[LeadJustification]:
        """Get justifications by category (fit, intent, timing)."""
        result = await self._session.execute(
            select(LeadJustification).where(
                and_(
                    LeadJustification.lead_id == lead_id,
                    LeadJustification.signal_category == category,
                )
            )
        )
        return list(result.scalars().all())


class CompetitorSignalRepository:
    """Repository for CompetitorSignal CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        competitor_id: UUID,
        signal_type: str,
        title: str,
        description: str | None = None,
        severity: str = "medium",
        primary_fact_id: UUID | None = None,
        supporting_fact_ids: list[UUID] | None = None,
        recommended_action: str | None = None,
    ) -> CompetitorSignal:
        """Create a competitor signal."""
        signal = CompetitorSignal(
            competitor_id=competitor_id,
            signal_type=signal_type,
            title=title,
            description=description,
            severity=severity,
            primary_fact_id=primary_fact_id,
            supporting_fact_ids=[str(fid) for fid in (supporting_fact_ids or [])],
            recommended_action=recommended_action,
        )
        self._session.add(signal)
        await self._session.commit()
        await self._session.refresh(signal)
        return signal

    async def get_for_competitor(
        self,
        competitor_id: UUID,
        acknowledged: bool | None = None,
    ) -> list[CompetitorSignal]:
        """Get signals for a competitor."""
        stmt = select(CompetitorSignal).where(
            CompetitorSignal.competitor_id == competitor_id
        )

        if acknowledged is not None:
            stmt = stmt.where(CompetitorSignal.is_acknowledged == acknowledged)

        stmt = stmt.order_by(CompetitorSignal.detected_at.desc())

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def acknowledge(self, signal_id: UUID) -> None:
        """Acknowledge a signal."""
        result = await self._session.execute(
            select(CompetitorSignal).where(CompetitorSignal.id == signal_id)
        )
        signal = result.scalar_one_or_none()

        if signal:
            signal.is_acknowledged = True
            signal.acknowledged_at = datetime.utcnow()
            await self._session.commit()


class MCPDataSourceRepository:
    """Repository for MCP data source registry."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register(
        self,
        name: str,
        source_type: SourceType,
        description: str = "",
        endpoint_url: str | None = None,
        config: dict[str, Any] | None = None,
        rate_limit_per_hour: int | None = None,
    ) -> MCPDataSource:
        """Register a new MCP data source."""
        # Check if already exists
        existing = await self.get_by_name(name)
        if existing:
            # Update existing
            existing.source_type = source_type
            existing.description = description
            existing.endpoint_url = endpoint_url
            existing.config = config or {}
            existing.rate_limit_per_hour = rate_limit_per_hour
            await self._session.commit()
            return existing

        source = MCPDataSource(
            name=name,
            source_type=source_type,
            description=description,
            endpoint_url=endpoint_url,
            config=config or {},
            rate_limit_per_hour=rate_limit_per_hour,
        )
        self._session.add(source)
        await self._session.commit()
        await self._session.refresh(source)
        return source

    async def get_by_name(self, name: str) -> MCPDataSource | None:
        """Get data source by name."""
        result = await self._session.execute(
            select(MCPDataSource).where(MCPDataSource.name == name)
        )
        return result.scalar_one_or_none()

    async def get_all_enabled(self) -> list[MCPDataSource]:
        """Get all enabled data sources."""
        result = await self._session.execute(
            select(MCPDataSource).where(MCPDataSource.is_enabled == True)  # noqa: E712
        )
        return list(result.scalars().all())

    async def update_health(
        self,
        name: str,
        is_healthy: bool,
    ) -> None:
        """Update health status of a data source."""
        source = await self.get_by_name(name)
        if source:
            source.is_healthy = is_healthy
            source.last_health_check = datetime.utcnow()
            await self._session.commit()

    async def record_sync(
        self,
        name: str,
        facts_produced: int,
        avg_confidence: float,
    ) -> None:
        """Record a sync operation."""
        source = await self.get_by_name(name)
        if source:
            source.last_sync = datetime.utcnow()
            source.total_facts_produced += facts_produced
            source.facts_today += facts_produced
            # Running average
            if source.avg_confidence > 0:
                source.avg_confidence = (source.avg_confidence + avg_confidence) / 2
            else:
                source.avg_confidence = avg_confidence
            await self._session.commit()


class KnowledgeWebService:
    """High-level service for Knowledge Web operations.

    Coordinates between repositories and provides business logic.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.facts = EvidencedFactRepository(session)
        self.entities = EntityRepository(session)
        self.relations = EntityRelationRepository(session)
        self.justifications = LeadJustificationRepository(session)
        self.competitor_signals = CompetitorSignalRepository(session)
        self.data_sources = MCPDataSourceRepository(session)

    async def ingest_mcp_result(
        self,
        mcp_result: Any,  # MCPQueryResult from packages.mcp.src.types
    ) -> list[EvidencedFact]:
        """Ingest facts from an MCP query result.

        Handles:
        - Fact deduplication
        - Entity creation/linking
        - Cross-source verification

        Args:
            mcp_result: MCPQueryResult from MCP server

        Returns:
            List of created/updated facts
        """
        created_facts = []

        for mcp_fact in mcp_result.facts:
            # Check for similar existing facts
            similar = await self.facts.find_similar(mcp_fact.claim)

            if similar:
                # Found similar - increment verification
                best_match = similar[0]
                await self.facts.increment_verification(best_match.id)
                created_facts.append(best_match)
            else:
                # Create new fact
                fact = await self.facts.create_from_mcp_fact(mcp_fact)
                created_facts.append(fact)

            # Handle related entities
            for entity_ref in mcp_result.entities:
                entity, _ = await self.entities.get_or_create(
                    entity_type=EntityType(entity_ref.entity_type.value),
                    name=entity_ref.name,
                    acra_uen=entity_ref.acra_uen,
                    website=entity_ref.website,
                    linkedin_url=entity_ref.linkedin_url,
                )

                # Link fact to entity
                link = FactEntityLink(
                    fact_id=created_facts[-1].id,
                    entity_id=entity.id,
                    role="subject",
                )
                self._session.add(link)

        await self._session.commit()

        return created_facts

    async def get_entity_profile(
        self,
        entity_id: UUID,
    ) -> dict[str, Any]:
        """Get complete profile for an entity.

        Includes all facts, relationships, and signals.
        """
        entity = await self.entities.get_by_id(entity_id)
        if not entity:
            return {}

        # Get facts
        facts = await self.facts.search(entity_id=entity_id, limit=100)

        # Get relations
        relations = await self.relations.get_relations(entity_id)

        return {
            "entity": {
                "id": str(entity.id),
                "type": entity.entity_type.value,
                "name": entity.name,
                "canonical_name": entity.canonical_name,
                "uen": entity.acra_uen,
                "website": entity.website,
                "description": entity.description,
                "attributes": entity.attributes,
                "fact_count": entity.fact_count,
                "confidence": entity.confidence,
            },
            "facts": [
                {
                    "id": str(f.id),
                    "claim": f.claim,
                    "type": f.fact_type.value,
                    "source": f.source_name,
                    "source_url": f.source_url,
                    "confidence": f.confidence,
                    "captured_at": f.captured_at.isoformat() if f.captured_at else None,
                }
                for f in facts
            ],
            "relations": [
                {
                    "id": str(r.id),
                    "type": r.relation_type.value,
                    "source_id": str(r.source_entity_id),
                    "target_id": str(r.target_entity_id),
                    "is_current": r.is_current,
                }
                for r in relations
            ],
        }

    async def build_lead_justification(
        self,
        lead_id: UUID,
        entity_id: UUID,
    ) -> list[LeadJustification]:
        """Build justifications for a lead based on entity facts.

        Analyzes facts about the entity and creates structured
        justifications for why this lead is qualified.
        """
        facts = await self.facts.search(entity_id=entity_id, limit=50)

        justifications = []

        # Categorize facts into signals
        for fact in facts:
            category = None
            signal_type = None
            impact = 0.5

            if fact.fact_type == FactType.HIRING:
                category = "intent"
                signal_type = "hiring_activity"
                impact = 0.7
            elif fact.fact_type == FactType.FUNDING:
                category = "timing"
                signal_type = "recent_funding"
                impact = 0.8
            elif fact.fact_type == FactType.EXPANSION:
                category = "intent"
                signal_type = "expansion_plans"
                impact = 0.6
            elif fact.fact_type == FactType.TECHNOLOGY:
                category = "fit"
                signal_type = "tech_stack_match"
                impact = 0.5
            elif fact.fact_type == FactType.COMPANY_INFO:
                category = "fit"
                signal_type = "company_profile"
                impact = 0.4

            if category and signal_type:
                justification = await self.justifications.create(
                    lead_id=lead_id,
                    signal_category=category,
                    signal_type=signal_type,
                    signal_description=fact.claim,
                    impact_score=impact * fact.confidence,
                    evidence_fact_ids=[fact.id],
                    evidence_summary=f"Source: {fact.source_name}",
                )
                justifications.append(justification)

        return justifications
