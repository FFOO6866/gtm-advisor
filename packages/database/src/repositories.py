"""Repository layer for GTM Advisor database operations.

Repositories provide a clean abstraction over raw SQLAlchemy queries.
Routers and services use repositories; they never write SQL directly.

Pattern (from agentic-os):
    repo = AnalysisRepository(session)
    await repo.save_result(analysis_id, gtm_result)
    result = await repo.get_by_id(analysis_id)
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.src.types import GTMAnalysisResult, LeadProfile, MarketInsight

from .models import Analysis, AnalysisStatus, AuditLog, Lead
from .models import MarketInsight as DBMarketInsight

logger = structlog.get_logger()


class AnalysisRepository:
    """CRUD operations for GTM analyses."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, analysis_id: UUID) -> Analysis | None:
        """Fetch analysis by primary key."""
        return await self._session.get(Analysis, analysis_id)

    async def list_for_company(
        self,
        company_id: UUID,
        limit: int = 20,
    ) -> list[Analysis]:
        """List analyses for a company, newest first."""
        result = await self._session.execute(
            select(Analysis)
            .where(Analysis.company_id == company_id)
            .order_by(Analysis.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        analysis_id: UUID,
        status: AnalysisStatus,
        progress: int = 0,
        current_agent: str | None = None,
        error: str | None = None,
    ) -> None:
        """Update the status and progress of an analysis."""
        values: dict = {"status": status, "progress": progress}
        if current_agent is not None:
            values["current_agent"] = current_agent
        if error is not None:
            values["error"] = error

        await self._session.execute(
            update(Analysis).where(Analysis.id == analysis_id).values(**values)
        )
        await self._session.commit()

    async def save_result(
        self,
        analysis_id: UUID,
        result: GTMAnalysisResult,
        processing_time_seconds: float = 0.0,
    ) -> None:
        """Persist a completed GTMAnalysisResult to the analysis record.

        Serialises all Pydantic sub-models to JSON-compatible dicts so they
        can be stored in the JSON columns of the Analysis table.
        """
        analysis = await self.get_by_id(analysis_id)
        if not analysis:
            logger.error("save_result_analysis_not_found", analysis_id=str(analysis_id))
            return

        analysis.status = AnalysisStatus.COMPLETED
        analysis.progress = 100
        analysis.current_agent = None
        analysis.completed_agents = result.agents_used
        analysis.executive_summary = result.executive_summary
        analysis.key_recommendations = result.key_recommendations
        analysis.market_insights = [
            m.model_dump(mode="json") for m in result.market_insights
        ]
        analysis.competitor_analysis = [
            c.model_dump(mode="json") for c in result.competitor_analysis
        ]
        analysis.customer_personas = [
            p.model_dump(mode="json") for p in result.customer_personas
        ]
        analysis.leads = [
            lead.model_dump(mode="json") for lead in result.leads
        ]
        analysis.campaign_brief = (
            result.campaign_brief.model_dump(mode="json")
            if result.campaign_brief and hasattr(result.campaign_brief, "model_dump")
            else result.campaign_brief
        )
        analysis.total_confidence = result.total_confidence
        analysis.processing_time_seconds = processing_time_seconds
        analysis.agents_used = result.agents_used

        await self._session.commit()

        logger.info(
            "analysis_result_saved",
            analysis_id=str(analysis_id),
            leads=len(result.leads),
            insights=len(result.market_insights),
            confidence=result.total_confidence,
        )

    async def reconstruct_result(self, analysis_id: UUID) -> GTMAnalysisResult | None:
        """Reconstruct a GTMAnalysisResult from the stored analysis record."""
        analysis = await self.get_by_id(analysis_id)
        if not analysis or analysis.status != AnalysisStatus.COMPLETED:
            return None

        return GTMAnalysisResult(
            id=analysis_id,
            company_id=analysis.company_id,
            executive_summary=analysis.executive_summary or "",
            key_recommendations=analysis.key_recommendations or [],
            market_insights=[
                MarketInsight(**m) for m in (analysis.market_insights or [])
            ],
            competitor_analysis=analysis.competitor_analysis or [],
            customer_personas=analysis.customer_personas or [],
            leads=[LeadProfile(**lead) for lead in (analysis.leads or [])],
            campaign_brief=analysis.campaign_brief,
            agents_used=analysis.agents_used or [],
            total_confidence=analysis.total_confidence or 0.0,
            processing_time_seconds=analysis.processing_time_seconds or 0.0,
        )


class LeadRepository:
    """CRUD operations for leads with upsert-based deduplication."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_batch(
        self,
        company_id: UUID,
        analysis_id: UUID,  # noqa: ARG002 — reserved for future partitioning
        leads: list[LeadProfile],
    ) -> int:
        """Upsert a batch of leads for a company.

        Deduplication key: (company_id, company_name, contact_email).
        Returns the count of leads upserted.
        """
        if not leads:
            return 0

        # Fetch existing leads for this company to check for duplicates
        existing_result = await self._session.execute(
            select(Lead).where(Lead.company_id == company_id)
        )
        # Dedup key uses the correct ORM column names
        existing_leads = {
            (lead.lead_company_name, lead.contact_email): lead
            for lead in existing_result.scalars().all()
        }

        inserted = 0
        updated = 0

        for lead_profile in leads:
            key = (lead_profile.company_name, lead_profile.contact_email)

            if key in existing_leads:
                # Update existing lead with new scores (scale 0-1 → 0-100 integer)
                existing = existing_leads[key]
                existing.fit_score = int(lead_profile.fit_score * 100)
                existing.intent_score = int(lead_profile.intent_score * 100)
                existing.overall_score = int(lead_profile.overall_score * 100)
                existing.qualification_reasons = lead_profile.pain_points
                existing.contact_linkedin = lead_profile.contact_linkedin
                # Store recommended_approach in notes (no dedicated column)
                if lead_profile.recommended_approach:
                    existing.notes = lead_profile.recommended_approach
                updated += 1
            else:
                # Insert new lead (scale 0-1 → 0-100 integer for score columns)
                db_lead = Lead(
                    company_id=company_id,
                    lead_company_name=lead_profile.company_name,
                    lead_company_website=lead_profile.website,
                    lead_company_industry=lead_profile.industry.value if lead_profile.industry else None,
                    lead_company_size=str(lead_profile.employee_count) if lead_profile.employee_count else None,
                    contact_name=lead_profile.contact_name,
                    contact_email=lead_profile.contact_email,
                    contact_title=lead_profile.contact_title,
                    contact_linkedin=lead_profile.contact_linkedin,
                    fit_score=int(lead_profile.fit_score * 100),
                    intent_score=int(lead_profile.intent_score * 100),
                    overall_score=int(lead_profile.overall_score * 100),
                    qualification_reasons=lead_profile.pain_points,
                    notes=lead_profile.recommended_approach,
                    source=lead_profile.source,
                    source_url=lead_profile.source_url,
                )
                self._session.add(db_lead)
                inserted += 1

        await self._session.commit()

        logger.info(
            "leads_upserted",
            company_id=str(company_id),
            inserted=inserted,
            updated=updated,
            total=inserted + updated,
        )

        return inserted + updated

    async def get_for_company(
        self,
        company_id: UUID,
        limit: int = 50,
        min_score: float = 0.0,
    ) -> list[LeadProfile]:
        """Get leads for a company, ordered by overall score."""
        result = await self._session.execute(
            select(Lead)
            .where(Lead.company_id == company_id, Lead.overall_score >= int(min_score * 100))
            .order_by(Lead.overall_score.desc())
            .limit(limit)
        )
        db_leads = result.scalars().all()

        return [
            LeadProfile(
                company_name=lead.lead_company_name or "",
                contact_name=lead.contact_name,
                contact_email=lead.contact_email,
                contact_title=lead.contact_title,
                website=lead.lead_company_website,
                fit_score=round((lead.fit_score or 0) / 100, 3),
                intent_score=round((lead.intent_score or 0) / 100, 3),
                overall_score=round((lead.overall_score or 0) / 100, 3),
                pain_points=lead.qualification_reasons or [],
                recommended_approach=lead.notes,
                source=lead.source or "platform",
                source_url=lead.source_url,
            )
            for lead in db_leads
        ]


class MarketInsightRepository:
    """CRUD operations for market insights."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_batch(
        self,
        company_id: UUID,
        analysis_id: UUID,  # noqa: ARG002 — reserved for future partitioning
        insights: list[MarketInsight],
    ) -> int:
        """Upsert market insights for a company analysis.

        Returns count of insights saved.
        """
        if not insights:
            return 0

        count = 0
        for insight in insights:
            # Map Pydantic MarketInsight → DBMarketInsight (actual model columns)
            # insight_type is NOT NULL — derive from category or default to "insight"
            insight_type = insight.category or "insight"
            # Merge key_findings + implications into full_content
            full_content_parts = []
            if insight.key_findings:
                full_content_parts.append("Key findings: " + "; ".join(insight.key_findings))
            if insight.implications:
                full_content_parts.append("Implications: " + "; ".join(insight.implications))
            if insight.recommendations:
                full_content_parts.append("Recommendations: " + "; ".join(insight.recommendations))
            # First source URL from sources list
            source_name = insight.sources[0] if insight.sources else None
            db_insight = DBMarketInsight(
                company_id=company_id,
                insight_type=insight_type,
                category=insight.category,
                title=insight.title,
                summary=insight.summary,
                full_content="\n\n".join(full_content_parts) if full_content_parts else None,
                relevance_score=insight.confidence,
                source_name=source_name,
                recommended_actions=insight.recommendations or [],
                related_agents=[],
            )
            self._session.add(db_insight)
            count += 1

        await self._session.commit()

        logger.info(
            "market_insights_saved",
            company_id=str(company_id),
            count=count,
        )

        return count


class AuditRepository:
    """Write-only repository for audit log entries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(
        self,
        event_type: str,
        entity_type: str,
        entity_id: str | None = None,
        user_id: UUID | None = None,
        company_id: UUID | None = None,
        details: dict | None = None,
    ) -> None:
        """Append an immutable audit log entry."""
        # Merge company_id into details (AuditLog has no company_id column)
        merged_details: dict = dict(details or {})
        if company_id is not None:
            merged_details["company_id"] = str(company_id)
        entry = AuditLog(
            event_type=event_type,
            resource_type=entity_type,
            resource_id=entity_id,
            user_id=user_id,
            details=merged_details,
            timestamp=datetime.now(UTC),
        )
        self._session.add(entry)
        await self._session.commit()
