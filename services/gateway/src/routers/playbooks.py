"""Playbooks router — pre-built GTM playbook templates."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.session import get_db_session
from packages.scoring.src.playbook_fit import PlaybookFitScorer

from ..services.playbook_service import PlaybookService

router = APIRouter()

class PlaybookRecommendRequest(BaseModel):
    lead_count: int = 0
    avg_lead_quality: float = 0.5
    has_competitor_signal: bool = False
    competitor_signal_age_hours: float = 999
    has_urgent_market_signal: bool = False
    client_industry: str = "technology"
    is_singapore_sme: bool = True
    is_new_market_entry: bool = False
    market_opportunity_rating: str = "amber"

@router.get("/{company_id}/playbooks")
async def list_playbooks(_company_id: UUID, db: AsyncSession = Depends(get_db_session)):
    svc = PlaybookService(db)
    playbooks = await svc.get_all_playbooks()
    return [{"id": str(pb.id), "playbook_type": pb.playbook_type, "name": pb.name, "description": pb.description, "best_for": pb.best_for, "steps_count": pb.steps_count, "duration_days": pb.duration_days, "success_rate_benchmark": pb.success_rate_benchmark, "is_singapore_specific": pb.is_singapore_specific} for pb in playbooks]

@router.post("/{company_id}/playbooks/recommend")
async def recommend_playbook(_company_id: UUID, body: PlaybookRecommendRequest):
    scorer = PlaybookFitScorer()
    recommendation = scorer.score(
        lead_count=body.lead_count,
        avg_lead_quality=body.avg_lead_quality,
        has_competitor_signal=body.has_competitor_signal,
        competitor_signal_age_hours=body.competitor_signal_age_hours,
        has_urgent_market_signal=body.has_urgent_market_signal,
        client_industry=body.client_industry,
        is_singapore_sme=body.is_singapore_sme,
        is_new_market_entry=body.is_new_market_entry,
        market_opportunity_rating=body.market_opportunity_rating,
    )
    return recommendation.to_dict()

@router.get("/methodology")
async def get_methodology():
    from packages.scoring.src.methodology import WhyUsMethodology
    return WhyUsMethodology.to_dict()
