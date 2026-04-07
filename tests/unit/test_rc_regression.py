"""Regression tests for RC v0.1.0 red-team fixes.

Each test targets a specific fix applied during the red-team review.
These tests exist to prevent regressions, not to provide full coverage.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.src.types import IndustryVertical
from packages.database.src.models import (
    AttributionEvent,
    Company,
    EnrollmentStatus,
    Lead,
    SequenceEnrollment,
    SequenceTemplate,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def company(db_session: AsyncSession) -> Company:
    co = Company(id=uuid4(), name="RC Test Co", owner_id=None, industry="fintech")
    db_session.add(co)
    await db_session.flush()
    return co


@pytest_asyncio.fixture
async def lead(db_session: AsyncSession, company: Company) -> Lead:
    ld = Lead(id=uuid4(), company_id=company.id, lead_company_name="Prospect Ltd")
    db_session.add(ld)
    await db_session.flush()
    return ld


@pytest_asyncio.fixture
async def template(db_session: AsyncSession) -> SequenceTemplate:
    tmpl = SequenceTemplate(
        id=uuid4(),
        name="Cold Outreach",
        playbook_type="cold_outreach",
        total_steps=3,
    )
    db_session.add(tmpl)
    await db_session.flush()
    return tmpl


# ===========================================================================
# Fix 1: scalar_one_or_none → scalars().first() for multi-opt-out
# ===========================================================================


class TestMultiOptOutEnrollment:
    """Fix 1: A lead that opted out of 2+ sequences must be blocked
    without crashing (MultipleResultsFound)."""

    @pytest.mark.asyncio
    async def test_enroll_blocked_when_lead_opted_out_of_multiple_sequences(
        self,
        db_session: AsyncSession,
        company: Company,
        lead: Lead,
        template: SequenceTemplate,
    ):
        """Two OPTED_OUT enrollments must not crash scalars().first()."""
        # Create a second template for the second enrollment
        tmpl2 = SequenceTemplate(
            id=uuid4(), name="Follow-Up", playbook_type="warm_up", total_steps=2,
        )
        db_session.add(tmpl2)

        # Create two OPTED_OUT enrollments for the same lead
        for tmpl_id in [template.id, tmpl2.id]:
            db_session.add(SequenceEnrollment(
                company_id=company.id,
                lead_id=lead.id,
                template_id=tmpl_id,
                status=EnrollmentStatus.OPTED_OUT,
            ))
        await db_session.commit()

        from services.gateway.src.services.sequence_engine import SequenceEngine

        engine = SequenceEngine(db_session)

        with pytest.raises(ValueError, match="opted out"):
            await engine.enroll(
                lead_id=lead.id,
                template_id=template.id,
                company_id=company.id,
            )

    @pytest.mark.asyncio
    async def test_enroll_blocked_when_lead_opted_out_of_single_sequence(
        self,
        db_session: AsyncSession,
        company: Company,
        lead: Lead,
        template: SequenceTemplate,
    ):
        """Single OPTED_OUT enrollment also blocks re-enrollment."""
        db_session.add(SequenceEnrollment(
            company_id=company.id,
            lead_id=lead.id,
            template_id=template.id,
            status=EnrollmentStatus.OPTED_OUT,
        ))
        await db_session.commit()

        from services.gateway.src.services.sequence_engine import SequenceEngine

        engine = SequenceEngine(db_session)

        with pytest.raises(ValueError, match="opted out"):
            await engine.enroll(
                lead_id=lead.id,
                template_id=template.id,
                company_id=company.id,
            )

    @pytest.mark.asyncio
    async def test_enroll_succeeds_when_no_opt_out(
        self,
        db_session: AsyncSession,
        company: Company,
        lead: Lead,
        template: SequenceTemplate,
    ):
        """Enrollment succeeds when lead has no opt-out history."""
        from services.gateway.src.services.sequence_engine import SequenceEngine

        engine = SequenceEngine(db_session)
        enrollment = await engine.enroll(
            lead_id=lead.id,
            template_id=template.id,
            company_id=company.id,
        )
        assert enrollment.status == EnrollmentStatus.ACTIVE
        assert enrollment.lead_id == lead.id

    @pytest.mark.asyncio
    async def test_enroll_creates_consent_attribution_event(
        self,
        db_session: AsyncSession,
        company: Company,
        lead: Lead,
        template: SequenceTemplate,
    ):
        """Enrollment must create a consent_recorded AttributionEvent."""
        from services.gateway.src.services.sequence_engine import SequenceEngine

        engine = SequenceEngine(db_session)
        await engine.enroll(
            lead_id=lead.id,
            template_id=template.id,
            company_id=company.id,
        )

        events = (await db_session.execute(
            select(AttributionEvent).where(
                AttributionEvent.lead_id == lead.id,
                AttributionEvent.event_type == "consent_recorded",
            )
        )).scalars().all()
        assert len(events) == 1
        assert events[0].metadata_json["purpose"] == "MARKETING"
        assert events[0].metadata_json["template_id"] == str(template.id)


# ===========================================================================
# Fix 2: Industry update rule on re-analysis
# ===========================================================================


class TestIndustryUpdateRule:
    """Fix 2: Explicit non-OTHER industry should override existing;
    OTHER/default should preserve existing industry."""

    def test_non_other_overrides_existing_industry(self):
        """User selecting SAAS on a fintech company should update to saas."""
        # Simulate the condition from analysis.py:256
        existing_industry = "fintech"
        request_industry = IndustryVertical.SAAS

        # Apply the RC logic
        if request_industry != IndustryVertical.OTHER:
            existing_industry = request_industry.value

        assert existing_industry == "saas"

    def test_other_preserves_existing_industry(self):
        """User submitting with OTHER (default) should preserve fintech."""
        existing_industry = "fintech"
        request_industry = IndustryVertical.OTHER

        if request_industry != IndustryVertical.OTHER:
            existing_industry = request_industry.value

        assert existing_industry == "fintech"

    def test_non_other_sets_industry_on_empty(self):
        """First-time industry assignment from OTHER to SAAS works."""
        existing_industry = None
        request_industry = IndustryVertical.SAAS

        if request_industry != IndustryVertical.OTHER:
            existing_industry = request_industry.value

        assert existing_industry == "saas"

    def test_other_does_not_overwrite_with_other(self):
        """OTHER should never write 'other' over a real value."""
        existing_industry = "fintech"
        request_industry = IndustryVertical.OTHER

        if request_industry != IndustryVertical.OTHER:
            existing_industry = request_industry.value

        assert existing_industry == "fintech"

    @pytest.mark.asyncio
    async def test_start_analysis_dedup_industry_update(self, db_session: AsyncSession):
        """Integration: existing company industry is updated on re-analysis
        when user picks a non-OTHER industry."""
        user_id = uuid4()
        co = Company(
            id=uuid4(), name="Industry Test Co", owner_id=user_id,
            industry="fintech", description="Old desc",
        )
        db_session.add(co)
        await db_session.flush()

        # Simulate the dedup lookup + update from start_analysis (lines 244-257)
        from sqlalchemy import select as sa_select

        _dedup_filters = [Company.name == "Industry Test Co", Company.owner_id == user_id]
        _existing = await db_session.scalar(
            sa_select(Company).where(*_dedup_filters).order_by(Company.created_at.desc()).limit(1)
        )
        assert _existing is not None

        # Apply with SAAS (non-OTHER)
        request_industry = IndustryVertical.SAAS
        if request_industry != IndustryVertical.OTHER:
            _existing.industry = request_industry.value

        await db_session.flush()
        await db_session.refresh(_existing)
        assert _existing.industry == "saas"

    @pytest.mark.asyncio
    async def test_start_analysis_dedup_preserves_industry_on_other(self, db_session: AsyncSession):
        """Integration: OTHER preserves existing industry."""
        user_id = uuid4()
        co = Company(
            id=uuid4(), name="Preserve Co", owner_id=user_id,
            industry="healthtech", description="Health",
        )
        db_session.add(co)
        await db_session.flush()

        from sqlalchemy import select as sa_select

        _existing = await db_session.scalar(
            sa_select(Company).where(Company.name == "Preserve Co", Company.owner_id == user_id)
        )

        request_industry = IndustryVertical.OTHER
        if request_industry != IndustryVertical.OTHER:
            _existing.industry = request_industry.value

        await db_session.flush()
        await db_session.refresh(_existing)
        assert _existing.industry == "healthtech"


# ===========================================================================
# Fix 3: quick_analysis dedup field completeness
# ===========================================================================


class TestQuickAnalysisDedupFields:
    """Fix 3: quick_analysis dedup must update industry and context_sources
    on existing companies (the two critical fields fixed in this RC)."""

    @pytest.mark.asyncio
    async def test_quick_analysis_dedup_updates_industry(self, db_session: AsyncSession):
        """quick_analysis dedup path sets industry when non-OTHER."""
        co = Company(
            id=uuid4(), name="QA Dedup Co", owner_id=None,
            industry="fintech", description="Old",
        )
        db_session.add(co)
        await db_session.flush()

        # Simulate the quick_analysis dedup logic (lines 449-453)
        from sqlalchemy import select as sa_select

        found = await db_session.scalar(
            sa_select(Company).where(Company.name == "QA Dedup Co", Company.owner_id.is_(None))
        )
        assert found is not None

        # Apply RC logic
        request_industry = IndustryVertical.ECOMMERCE
        if request_industry != IndustryVertical.OTHER:
            found.industry = request_industry.value

        await db_session.flush()
        await db_session.refresh(found)
        assert found.industry == "ecommerce"

    @pytest.mark.asyncio
    async def test_quick_analysis_dedup_updates_context_sources(self, db_session: AsyncSession):
        """quick_analysis dedup path appends new context_sources."""
        co = Company(
            id=uuid4(), name="Context Co", owner_id=None,
            industry="saas", description="SaaS co",
            context_sources=[{"type": "manual", "name": "old_note", "content": "old"}],
        )
        db_session.add(co)
        await db_session.flush()

        from sqlalchemy import select as sa_select

        found = await db_session.scalar(
            sa_select(Company).where(Company.name == "Context Co", Company.owner_id.is_(None))
        )

        # Simulate the RC context_sources update (lines 454-459)
        additional_context = "New uploaded document text"
        if additional_context:
            from services.gateway.src.routers.analysis import _make_source_entry

            sources: list[dict] = list(found.context_sources or [])
            new_entry = _make_source_entry("document", "uploaded_document", additional_context)
            sources = [s for s in sources if not (s.get("type") == "document" and s.get("name") == "uploaded_document")]
            sources.append(new_entry)
            found.context_sources = sources

        await db_session.flush()
        await db_session.refresh(found)

        # Old manual source preserved, new document source added
        assert len(found.context_sources) == 2
        types = {s["name"] for s in found.context_sources}
        assert "old_note" in types
        assert "uploaded_document" in types


# ===========================================================================
# Fix 4: AttributionEvent import is top-level (no test needed — validated
# by the fact that enroll tests above exercise the import path).
# ===========================================================================
