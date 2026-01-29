"""Export API endpoints for PDF and JSON reports."""

import io
import json
from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.database.src.models import (
    Analysis,
    Company,
    Competitor,
    ICP,
    Lead,
    Campaign,
    MarketInsight,
)
from packages.database.src.session import get_db_session

logger = structlog.get_logger()
router = APIRouter()


@router.get("/{company_id}/analysis/{analysis_id}/json")
async def export_analysis_json(
    company_id: UUID,
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    """Export analysis results as JSON."""
    analysis = await db.get(Analysis, analysis_id)
    if not analysis or analysis.company_id != company_id:
        raise HTTPException(status_code=404, detail="Analysis not found")

    company = await db.get(Company, company_id)

    export_data = {
        "export_type": "gtm_analysis",
        "exported_at": datetime.utcnow().isoformat(),
        "company": {
            "name": company.name if company else "Unknown",
            "website": company.website if company else None,
            "industry": company.industry if company else None,
        },
        "analysis": {
            "id": str(analysis.id),
            "status": analysis.status.value if analysis.status else "unknown",
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
            "processing_time_seconds": analysis.processing_time_seconds,
            "total_confidence": analysis.total_confidence,
            "agents_used": analysis.agents_used,
        },
        "results": {
            "executive_summary": analysis.executive_summary,
            "key_recommendations": analysis.key_recommendations,
            "market_insights": analysis.market_insights,
            "competitor_analysis": analysis.competitor_analysis,
            "customer_personas": analysis.customer_personas,
            "leads": analysis.leads,
            "campaign_brief": analysis.campaign_brief,
        },
        "decision_metrics": {
            "algorithm_decisions": analysis.algorithm_decisions,
            "llm_decisions": analysis.llm_decisions,
            "tool_calls": analysis.tool_calls,
        },
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="gtm_analysis_{analysis_id}.json"'
        },
    )


@router.get("/{company_id}/competitors/json")
async def export_competitors_json(
    company_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    """Export all competitors as JSON."""
    query = (
        select(Competitor)
        .where(Competitor.company_id == company_id, Competitor.is_active == True)
        .order_by(Competitor.threat_level.desc())
    )
    result = await db.execute(query)
    competitors = result.scalars().all()

    company = await db.get(Company, company_id)

    export_data = {
        "export_type": "competitor_analysis",
        "exported_at": datetime.utcnow().isoformat(),
        "company": company.name if company else "Unknown",
        "total_competitors": len(competitors),
        "competitors": [
            {
                "name": c.name,
                "website": c.website,
                "threat_level": c.threat_level.value if c.threat_level else "medium",
                "positioning": c.positioning,
                "swot": {
                    "strengths": c.strengths or [],
                    "weaknesses": c.weaknesses or [],
                    "opportunities": c.opportunities or [],
                    "threats": c.threats or [],
                },
                "battle_card": {
                    "our_advantages": c.our_advantages or [],
                    "their_advantages": c.their_advantages or [],
                    "objection_handlers": c.key_objection_handlers or [],
                },
                "pricing_info": c.pricing_info,
                "last_updated": c.last_updated.isoformat() if c.last_updated else None,
            }
            for c in competitors
        ],
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="competitors_{company_id}.json"'
        },
    )


@router.get("/{company_id}/battlecards/json")
async def export_battlecards_json(
    company_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    """Export all battle cards as JSON."""
    query = (
        select(Competitor)
        .where(Competitor.company_id == company_id, Competitor.is_active == True)
        .order_by(Competitor.threat_level.desc())
    )
    result = await db.execute(query)
    competitors = result.scalars().all()

    company = await db.get(Company, company_id)

    battle_cards = []
    for c in competitors:
        win_strategies = []
        for weakness in (c.weaknesses or [])[:3]:
            win_strategies.append(f"Exploit weakness: {weakness}")
        for advantage in (c.our_advantages or [])[:2]:
            win_strategies.append(f"Leverage strength: {advantage}")

        battle_cards.append({
            "competitor": c.name,
            "threat_level": c.threat_level.value if c.threat_level else "medium",
            "our_advantages": c.our_advantages or [],
            "their_advantages": c.their_advantages or [],
            "objection_handlers": c.key_objection_handlers or [],
            "win_strategies": win_strategies,
            "key_differentiators": [
                adv for adv in (c.our_advantages or [])[:3]
            ],
        })

    export_data = {
        "export_type": "battle_cards",
        "exported_at": datetime.utcnow().isoformat(),
        "company": company.name if company else "Unknown",
        "battle_cards": battle_cards,
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="battlecards_{company_id}.json"'
        },
    )


@router.get("/{company_id}/icps/json")
async def export_icps_json(
    company_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    """Export ICPs and personas as JSON."""
    query = (
        select(ICP)
        .options(selectinload(ICP.personas))
        .where(ICP.company_id == company_id, ICP.is_active == True)
        .order_by(ICP.fit_score.desc())
    )
    result = await db.execute(query)
    icps = result.scalars().unique().all()

    company = await db.get(Company, company_id)

    export_data = {
        "export_type": "icps_and_personas",
        "exported_at": datetime.utcnow().isoformat(),
        "company": company.name if company else "Unknown",
        "icps": [
            {
                "name": icp.name,
                "description": icp.description,
                "fit_score": icp.fit_score,
                "characteristics": {
                    "company_size": icp.company_size,
                    "revenue_range": icp.revenue_range,
                    "industry": icp.industry,
                    "tech_stack": icp.tech_stack,
                },
                "buying_triggers": icp.buying_triggers or [],
                "pain_points": icp.pain_points or [],
                "needs": icp.needs or [],
                "matching_companies": icp.matching_companies_count,
                "personas": [
                    {
                        "name": p.name,
                        "role": p.role,
                        "demographics": {
                            "age_range": p.age_range,
                            "experience": p.experience_years,
                            "education": p.education,
                        },
                        "goals": p.goals or [],
                        "challenges": p.challenges or [],
                        "objections": p.objections or [],
                        "channels": p.preferred_channels or [],
                        "messaging_hooks": p.messaging_hooks or [],
                    }
                    for p in icp.personas
                    if p.is_active
                ],
            }
            for icp in icps
        ],
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="icps_{company_id}.json"'
        },
    )


@router.get("/{company_id}/leads/json")
async def export_leads_json(
    company_id: UUID,
    min_score: int = Query(default=0, ge=0, le=100),
    status: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    """Export leads as JSON."""
    from packages.database.src.models import LeadStatus

    query = select(Lead).where(Lead.company_id == company_id)

    if min_score > 0:
        query = query.where(Lead.overall_score >= min_score)
    if status:
        query = query.where(Lead.status == LeadStatus(status))

    query = query.order_by(Lead.overall_score.desc())

    result = await db.execute(query)
    leads = result.scalars().all()

    company = await db.get(Company, company_id)

    export_data = {
        "export_type": "leads",
        "exported_at": datetime.utcnow().isoformat(),
        "company": company.name if company else "Unknown",
        "total_leads": len(leads),
        "filters_applied": {
            "min_score": min_score,
            "status": status,
        },
        "leads": [
            {
                "company_name": lead.lead_company_name,
                "website": lead.lead_company_website,
                "industry": lead.lead_company_industry,
                "size": lead.lead_company_size,
                "description": lead.lead_company_description,
                "contact": {
                    "name": lead.contact_name,
                    "title": lead.contact_title,
                    "email": lead.contact_email,
                    "linkedin": lead.contact_linkedin,
                },
                "scores": {
                    "fit": lead.fit_score,
                    "intent": lead.intent_score,
                    "overall": lead.overall_score,
                },
                "status": lead.status.value if lead.status else "new",
                "qualification_reasons": lead.qualification_reasons or [],
                "source": lead.source,
                "tags": lead.tags or [],
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
            }
            for lead in leads
        ],
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="leads_{company_id}.json"'
        },
    )


@router.get("/{company_id}/campaigns/{campaign_id}/json")
async def export_campaign_json(
    company_id: UUID,
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    """Export a campaign with all content assets as JSON."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    company = await db.get(Company, company_id)

    export_data = {
        "export_type": "campaign",
        "exported_at": datetime.utcnow().isoformat(),
        "company": company.name if company else "Unknown",
        "campaign": {
            "name": campaign.name,
            "description": campaign.description,
            "objective": campaign.objective,
            "status": campaign.status.value if campaign.status else "draft",
            "target_audience": {
                "personas": campaign.target_personas or [],
                "industries": campaign.target_industries or [],
                "company_sizes": campaign.target_company_sizes or [],
            },
            "messaging": {
                "key_messages": campaign.key_messages or [],
                "value_propositions": campaign.value_propositions or [],
                "call_to_action": campaign.call_to_action,
            },
            "channels": campaign.channels or [],
            "budget": {
                "amount": campaign.budget,
                "currency": campaign.currency,
            },
            "timeline": {
                "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
                "end_date": campaign.end_date.isoformat() if campaign.end_date else None,
            },
            "content_assets": {
                "email_templates": campaign.email_templates or [],
                "linkedin_posts": campaign.linkedin_posts or [],
                "ad_copy": campaign.ad_copy or [],
                "landing_page": campaign.landing_page_copy,
                "blog_outlines": campaign.blog_outlines or [],
            },
            "metrics": campaign.metrics or {},
        },
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="campaign_{campaign_id}.json"'
        },
    )


@router.get("/{company_id}/full-report/json")
async def export_full_report_json(
    company_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    """Export a complete GTM report with all data."""
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Get latest analysis
    analysis_query = (
        select(Analysis)
        .where(Analysis.company_id == company_id)
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    analysis_result = await db.execute(analysis_query)
    analysis = analysis_result.scalars().first()

    # Get competitors
    competitors_query = select(Competitor).where(
        Competitor.company_id == company_id, Competitor.is_active == True
    )
    competitors = (await db.execute(competitors_query)).scalars().all()

    # Get ICPs with personas
    icps_query = (
        select(ICP)
        .options(selectinload(ICP.personas))
        .where(ICP.company_id == company_id, ICP.is_active == True)
    )
    icps = (await db.execute(icps_query)).scalars().unique().all()

    # Get top leads
    leads_query = (
        select(Lead)
        .where(Lead.company_id == company_id)
        .order_by(Lead.overall_score.desc())
        .limit(20)
    )
    leads = (await db.execute(leads_query)).scalars().all()

    # Get active campaigns
    campaigns_query = select(Campaign).where(Campaign.company_id == company_id)
    campaigns = (await db.execute(campaigns_query)).scalars().all()

    # Get recent insights
    insights_query = (
        select(MarketInsight)
        .where(MarketInsight.company_id == company_id, MarketInsight.is_archived == False)
        .order_by(MarketInsight.created_at.desc())
        .limit(10)
    )
    insights = (await db.execute(insights_query)).scalars().all()

    export_data = {
        "export_type": "full_gtm_report",
        "exported_at": datetime.utcnow().isoformat(),
        "company_profile": {
            "name": company.name,
            "website": company.website,
            "description": company.description,
            "industry": company.industry,
            "founded": company.founded_year,
            "headquarters": company.headquarters,
            "size": company.employee_count,
            "funding": company.funding_stage,
            "value_proposition": company.value_proposition,
            "target_markets": company.target_markets,
            "tech_stack": company.tech_stack,
            "products": company.products,
        },
        "analysis_summary": {
            "executive_summary": analysis.executive_summary if analysis else None,
            "key_recommendations": analysis.key_recommendations if analysis else [],
            "confidence_score": analysis.total_confidence if analysis else 0,
            "completed_at": analysis.completed_at.isoformat() if analysis and analysis.completed_at else None,
        } if analysis else None,
        "competitive_landscape": {
            "total_competitors": len(competitors),
            "high_threat": sum(1 for c in competitors if c.threat_level and c.threat_level.value == "high"),
            "competitors": [
                {
                    "name": c.name,
                    "threat_level": c.threat_level.value if c.threat_level else "medium",
                    "positioning": c.positioning,
                    "strengths": c.strengths[:3] if c.strengths else [],
                    "weaknesses": c.weaknesses[:3] if c.weaknesses else [],
                }
                for c in competitors
            ],
        },
        "target_customers": {
            "icps": [
                {
                    "name": icp.name,
                    "fit_score": icp.fit_score,
                    "characteristics": {
                        "size": icp.company_size,
                        "revenue": icp.revenue_range,
                        "industry": icp.industry,
                    },
                    "pain_points": icp.pain_points[:3] if icp.pain_points else [],
                    "personas_count": len([p for p in icp.personas if p.is_active]),
                }
                for icp in icps
            ],
        },
        "lead_pipeline": {
            "total_leads": len(leads),
            "high_score_leads": sum(1 for l in leads if l.overall_score and l.overall_score > 80),
            "top_leads": [
                {
                    "company": l.lead_company_name,
                    "score": l.overall_score,
                    "status": l.status.value if l.status else "new",
                }
                for l in leads[:10]
            ],
        },
        "campaigns": {
            "total": len(campaigns),
            "active": sum(1 for c in campaigns if c.status and c.status.value == "active"),
            "campaigns": [
                {
                    "name": c.name,
                    "objective": c.objective,
                    "status": c.status.value if c.status else "draft",
                    "channels": c.channels[:3] if c.channels else [],
                }
                for c in campaigns
            ],
        },
        "market_intelligence": {
            "recent_insights": [
                {
                    "type": i.insight_type,
                    "title": i.title,
                    "impact": i.impact_level,
                    "summary": i.summary[:200] if i.summary else None,
                }
                for i in insights
            ],
        },
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="gtm_report_{company_id}.json"'
        },
    )
