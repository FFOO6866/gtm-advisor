"""Campaign management API endpoints."""

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import Campaign, CampaignStatus, Company
from packages.database.src.models import GeneratedContent as GeneratedContentModel
from packages.database.src.session import get_db_session

from ..agents_registry import get_agent_class
from ..auth.dependencies import get_optional_user, validate_company_access
from ..auth.models import User
from ..schemas.campaigns import (
    CampaignCreate,
    CampaignListResponse,
    CampaignResponse,
    CampaignUpdate,
)
from ..utils import verify_company_exists

logger = structlog.get_logger()
router = APIRouter()


def campaign_to_response(campaign: Campaign) -> CampaignResponse:
    """Convert database model to response schema."""
    return CampaignResponse(
        id=campaign.id,
        company_id=campaign.company_id,
        icp_id=campaign.icp_id,
        name=campaign.name,
        description=campaign.description,
        objective=campaign.objective or "lead_gen",
        status=campaign.status.value if campaign.status else "draft",
        target_personas=campaign.target_personas or [],
        target_industries=campaign.target_industries or [],
        target_company_sizes=campaign.target_company_sizes or [],
        key_messages=campaign.key_messages or [],
        value_propositions=campaign.value_propositions or [],
        call_to_action=campaign.call_to_action,
        channels=campaign.channels or [],
        email_templates=campaign.email_templates or [],
        linkedin_posts=campaign.linkedin_posts or [],
        ad_copy=campaign.ad_copy or [],
        landing_page_copy=campaign.landing_page_copy,
        blog_outlines=campaign.blog_outlines or [],
        budget=campaign.budget,
        currency=campaign.currency or "SGD",
        start_date=campaign.start_date,
        end_date=campaign.end_date,
        metrics=campaign.metrics or {},
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


@router.get("/{company_id}/campaigns", response_model=CampaignListResponse)
async def list_campaigns(
    company_id: UUID,
    status: str | None = Query(default=None, pattern="^(draft|active|paused|completed)$"),
    objective: str | None = Query(
        default=None, pattern="^(awareness|lead_gen|conversion|retention)$"
    ),
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> CampaignListResponse:
    """List all campaigns for a company."""
    await validate_company_access(company_id, current_user, db)
    query = select(Campaign).where(Campaign.company_id == company_id)

    if status:
        query = query.where(Campaign.status == CampaignStatus(status))
    if objective:
        query = query.where(Campaign.objective == objective)

    query = query.order_by(Campaign.created_at.desc())

    result = await db.execute(query)
    campaigns = result.scalars().all()

    # Get counts
    by_status = {}
    by_objective = {}
    total_budget = 0.0

    for campaign in campaigns:
        status_val = campaign.status.value if campaign.status else "draft"
        by_status[status_val] = by_status.get(status_val, 0) + 1

        obj_val = campaign.objective or "lead_gen"
        by_objective[obj_val] = by_objective.get(obj_val, 0) + 1

        if campaign.budget:
            total_budget += campaign.budget

    return CampaignListResponse(
        campaigns=[campaign_to_response(c) for c in campaigns],
        total=len(campaigns),
        by_status=by_status,
        by_objective=by_objective,
        total_budget=total_budget,
    )


@router.post("/{company_id}/campaigns", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    company_id: UUID,
    data: CampaignCreate,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Create a new campaign."""
    await validate_company_access(company_id, current_user, db)
    # Verify company exists
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    campaign = Campaign(
        company_id=company_id,
        icp_id=data.icp_id,
        name=data.name,
        description=data.description,
        objective=data.objective,
        target_personas=data.target_personas,
        target_industries=data.target_industries,
        target_company_sizes=data.target_company_sizes,
        key_messages=data.key_messages,
        value_propositions=data.value_propositions,
        call_to_action=data.call_to_action,
        channels=data.channels,
        budget=data.budget,
        currency=data.currency,
        start_date=data.start_date,
        end_date=data.end_date,
    )

    db.add(campaign)
    await db.flush()

    logger.info("campaign_created", campaign_id=str(campaign.id), name=campaign.name)
    return campaign_to_response(campaign)


@router.get("/{company_id}/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    company_id: UUID,
    campaign_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Get a specific campaign."""
    await validate_company_access(company_id, current_user, db)
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return campaign_to_response(campaign)


@router.patch("/{company_id}/campaigns/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    company_id: UUID,
    campaign_id: UUID,
    data: CampaignUpdate,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Update a campaign."""
    await validate_company_access(company_id, current_user, db)
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    update_data = data.model_dump(exclude_unset=True)

    # Handle status conversion
    if "status" in update_data:
        update_data["status"] = CampaignStatus(update_data["status"])

    for field, value in update_data.items():
        setattr(campaign, field, value)

    await db.flush()

    logger.info("campaign_updated", campaign_id=str(campaign_id))
    return campaign_to_response(campaign)


@router.delete("/{company_id}/campaigns/{campaign_id}", status_code=204)
async def delete_campaign(
    company_id: UUID,
    campaign_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a campaign."""
    await validate_company_access(company_id, current_user, db)
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    await db.delete(campaign)
    await db.flush()

    logger.info("campaign_deleted", campaign_id=str(campaign_id))


@router.post("/{company_id}/campaigns/{campaign_id}/activate", response_model=CampaignResponse)
async def activate_campaign(
    company_id: UUID,
    campaign_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Activate a campaign."""
    await validate_company_access(company_id, current_user, db)
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = CampaignStatus.ACTIVE
    if not campaign.start_date:
        campaign.start_date = datetime.utcnow()

    await db.flush()

    logger.info("campaign_activated", campaign_id=str(campaign_id))
    return campaign_to_response(campaign)


@router.post("/{company_id}/campaigns/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    company_id: UUID,
    campaign_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Pause a campaign."""
    await validate_company_access(company_id, current_user, db)
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = CampaignStatus.PAUSED
    await db.flush()

    logger.info("campaign_paused", campaign_id=str(campaign_id))
    return campaign_to_response(campaign)


@router.post("/{company_id}/campaigns/{campaign_id}/complete", response_model=CampaignResponse)
async def complete_campaign(
    company_id: UUID,
    campaign_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Mark a campaign as completed."""
    await validate_company_access(company_id, current_user, db)
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = CampaignStatus.COMPLETED
    if not campaign.end_date:
        campaign.end_date = datetime.utcnow()

    await db.flush()

    logger.info("campaign_completed", campaign_id=str(campaign_id))
    return campaign_to_response(campaign)


@router.post(
    "/{company_id}/campaigns/{campaign_id}/duplicate",
    response_model=CampaignResponse,
    status_code=201,
)
async def duplicate_campaign(
    company_id: UUID,
    campaign_id: UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Duplicate a campaign."""
    await validate_company_access(company_id, current_user, db)
    campaign = await db.get(Campaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    new_campaign = Campaign(
        company_id=company_id,
        icp_id=campaign.icp_id,
        name=f"{campaign.name} (Copy)",
        description=campaign.description,
        objective=campaign.objective,
        target_personas=campaign.target_personas,
        target_industries=campaign.target_industries,
        target_company_sizes=campaign.target_company_sizes,
        key_messages=campaign.key_messages,
        value_propositions=campaign.value_propositions,
        call_to_action=campaign.call_to_action,
        channels=campaign.channels,
        email_templates=campaign.email_templates,
        linkedin_posts=campaign.linkedin_posts,
        ad_copy=campaign.ad_copy,
        landing_page_copy=campaign.landing_page_copy,
        blog_outlines=campaign.blog_outlines,
        budget=campaign.budget,
        currency=campaign.currency,
        # Don't copy dates or metrics
    )

    db.add(new_campaign)
    await db.flush()

    logger.info("campaign_duplicated", original_id=str(campaign_id), new_id=str(new_campaign.id))
    return campaign_to_response(new_campaign)


# ============================================================================
# Content Generation
# ============================================================================


class ContentGenerationRequest(BaseModel):
    """Request to generate marketing content."""

    content_type: str = Field(..., pattern="^(linkedin|email|blog|ad)$")
    topic: str = Field(..., min_length=1)
    tone: str = Field(default="professional", pattern="^(professional|conversational|bold)$")
    target_persona: str | None = None
    include_cta: bool = True
    key_points: list[str] | None = None
    variations: int = Field(default=3, ge=1, le=5)


class GeneratedContentResponse(BaseModel):
    """Generated content item - matches frontend GeneratedContent interface."""

    id: str
    content_type: str  # 'linkedin', 'email', 'blog', 'ad'
    content: str
    tone: str
    target_persona: str
    created_at: str


async def generate_content_with_ai(
    company: Company,
    request: ContentGenerationRequest,
) -> list[str] | None:
    """Generate content using the Campaign Architect agent.

    CampaignPlanOutput structure:
    - content_pieces: list[ContentPiece] where ContentPiece has: type, title, content, target_persona

    Returns list of content strings, or None if AI generation fails.
    """
    try:
        agent_class = get_agent_class("campaign-architect")
        if not agent_class:
            logger.warning("campaign_architect_not_available")
            return None

        agent = agent_class()

        # Build context with company info
        context = {
            "company_id": str(company.id),
            "company_name": company.name,
            "industry": company.industry or "Technology",
            "description": company.description or "",
            "content_type": request.content_type,
            "tone": request.tone,
            "target_persona": request.target_persona or "Business Decision Makers",
            "include_cta": request.include_cta,
            "key_points": request.key_points or [],
        }

        task = f"Generate {request.variations} {request.content_type} content pieces about '{request.topic}' in a {request.tone} tone for {context['target_persona']}"

        result = await agent.run(task, context=context)

        # CampaignPlanOutput has content_pieces: list[ContentPiece]
        # ContentPiece has: type, title, content, target_persona, call_to_action
        content_pieces = []

        if hasattr(result, "content_pieces"):
            pieces = result.content_pieces
        elif hasattr(result, "model_dump"):
            data = result.model_dump()
            pieces = data.get("content_pieces", [])
        else:
            pieces = []

        # Filter by requested content type and extract content
        for piece in pieces:
            if isinstance(piece, dict):
                piece_type = piece.get("type", "")
                piece_content = piece.get("content", "")
            else:
                piece_type = getattr(piece, "type", "")
                piece_content = getattr(piece, "content", "")

            # Match content type (linkedin, email, blog, ad, etc.)
            type_match = (
                piece_type.lower() == request.content_type.lower()
                or request.content_type.lower() in piece_type.lower()
            )

            if type_match and piece_content:
                content_pieces.append(piece_content)

        # If we found matching content, return it
        if content_pieces:
            # Return up to requested variations
            result_list = content_pieces[: request.variations]

            # If we need more, we can't just duplicate - return what we have
            logger.info(
                "ai_content_generated",
                company_id=str(company.id),
                requested=request.variations,
                generated=len(result_list),
            )
            return result_list if result_list else None

        # No matching content pieces found
        logger.warning(
            "no_matching_content_pieces",
            content_type=request.content_type,
            pieces_found=len(pieces),
        )
        return None

    except Exception as e:
        logger.warning("ai_content_generation_failed", error=str(e))
        return None


def get_template_content(
    content_type: str,
    tone: str,
    topic: str,
    company_name: str,
    target_persona: str,
    variations: int,
) -> list[str]:
    """Generate content from templates as fallback.

    Note: Templates are designed to be honest and not contain fabricated claims.
    """
    templates = {
        "linkedin": {
            "professional": [
                f"📊 {topic}\n\nAt {company_name}, we're focused on helping companies leverage strategic positioning to drive growth.\n\nKey areas we focus on:\n• Data-driven decision making\n• Customer-centric approaches\n• Efficient growth strategies\n\nWhat strategies have worked for your organization?\n\n#BusinessStrategy #Innovation #Growth",
                f"The landscape of {topic.lower()} is evolving rapidly.\n\nHere's what we're seeing successful organizations do differently:\n\n1️⃣ Investing in automation\n2️⃣ Prioritizing customer experience\n3️⃣ Building data-driven cultures\n4️⃣ Embracing agile methodologies\n\n{company_name} helps companies navigate this transformation.\n\n#Leadership #Transformation",
                f"🎯 {topic}\n\nIn our experience working with {target_persona}s, we've observed some patterns:\n\n✅ Start with clear objectives\n✅ Measure what matters\n✅ Iterate based on feedback\n✅ Scale what works\n\nSimple principles that drive results.\n\n#BestPractices #Growth",
            ],
            "conversational": [
                f"Let's talk about {topic.lower()}.\n\nI've been thinking a lot about this lately, and here's what I've noticed:\n\nThe companies that are winning aren't always the biggest or the fastest. They're the ones that truly understand their customers.\n\nAt {company_name}, we help {target_persona}s do exactly that.\n\n🤔 What's your take?\n\n#Thoughts #Business",
                f"Real talk: {topic.lower()} doesn't have to be complicated.\n\nHere's our approach at {company_name}:\n\n→ Focus on fundamentals\n→ Listen to customers\n→ Build relationships\n→ Measure what matters\n\nWhat's working for you? Let's discuss 👇",
                f"📖 When we started working on {topic.lower()} at {company_name}, we learned a lot along the way.\n\nOne key insight:\n\nFocusing on ONE thing at a time makes a real difference.\n\nWhat's your one priority right now?",
            ],
            "bold": [
                f"🔥 Let's be honest about {topic.lower()}:\n\nMany approaches don't deliver results.\n\nCommon pitfalls:\n❌ Vanity metrics\n❌ Copycat strategies\n❌ Short-term thinking\n\nAt {company_name}, we focus on:\n✅ Real impact\n✅ Differentiation\n✅ Sustainable growth\n\nWhich approach resonates with you?",
                f"PAUSE. 🛑\n\nQuick question:\n\nIs your approach to {topic.lower()} delivering the results you want?\n\nOr are you just staying busy?\n\n{company_name} helps {target_persona}s find clarity.\n\n👇 Share your thoughts below.",
                f"An honest take on {topic.lower()}:\n\nMany strategies don't achieve their goals.\n\nNot because they're bad ideas.\n\nBut because execution is challenging.\n\nWhat {company_name} focuses on:\n\n💪 Clear priorities\n💪 Disciplined execution\n💪 Consistent action",
            ],
        },
        "email": {
            "professional": [
                f"Subject: {topic} - Insights for {target_persona}s\n\nDear [Name],\n\nI hope this message finds you well.\n\nI'm reaching out from {company_name} to share some thoughts about {topic.lower()} that may be relevant to your organization.\n\nSome areas we're currently exploring:\n\n• Current market dynamics\n• Strategic opportunities\n• Implementation approaches\n\nWould you have 15 minutes this week for a brief conversation?\n\nBest regards,\n[Your Name]\n{company_name}",
            ],
            "conversational": [
                f"Subject: Quick thought on {topic.lower()}\n\nHey [Name],\n\nHope you're having a great week!\n\nI'm [Your Name] from {company_name}, and I've been thinking about how {target_persona}s like yourself approach {topic.lower()}.\n\nA few things caught our attention:\n\n1. The market is moving fast\n2. New approaches are emerging\n3. There might be a fit for you\n\nFree for a quick coffee chat this week?\n\nCheers,\n[Your Name]",
            ],
            "bold": [
                f"Subject: {topic} - Important Insights for {target_persona}s\n\nHi [Name],\n\nI'll be direct: the landscape of {topic.lower()} is changing.\n\nCompanies that adapt proactively tend to come out ahead.\n\n{company_name} focuses on helping {target_persona}s navigate these changes.\n\n15 minutes for a conversation?\n\nAre you in?\n\n[Your Name]",
            ],
        },
        "blog": {
            "professional": [
                f"# {topic}: A Guide for {target_persona}s\n\n## Introduction\n\nUnderstanding {topic.lower()} has become increasingly important for business success. At {company_name}, we work with {target_persona}s to navigate this landscape.\n\n## Why This Matters\n\nOrganizations that develop expertise in {topic.lower()} often see improved outcomes.\n\n## Key Strategies\n\n### 1. Start with Data\nEvery successful initiative begins with understanding your baseline.\n\n### 2. Focus on Customer Value\nThe best strategies center on delivering real value.\n\n### 3. Iterate and Improve\nBuild in feedback loops from day one.\n\n## Conclusion\n\nSuccess requires commitment, strategy, and execution. {company_name} can help you explore your options.\n\n---\n*Ready to learn more? [Contact us] for a consultation.*",
            ],
            "conversational": [
                f"# What {target_persona}s Should Consider About {topic}\n\nLet me share some observations.\n\nAt {company_name}, we've learned a lot about {topic.lower()} over time.\n\n## A Common Challenge\n\nMany {target_persona}s focus on tactics before strategy.\n\n## What We've Found Works\n\nBased on our experience:\n\n**1. Simple often beats complex**\n\n**2. Consistency matters**\n\n**3. Feedback is valuable**\n\n## Your Turn\n\nWhat's your biggest challenge with {topic.lower()}?",
            ],
            "bold": [
                f"# An Honest Look at {topic} for {target_persona}s\n\n**Let's be real.**\n\nNot all advice about {topic.lower()} is helpful.\n\n## Why Some Strategies Don't Work\n\n- Lack of focus is a common issue\n- Execution is often harder than planning\n- Quick fixes rarely work\n\n## A Different Approach\n\nFocus on fundamentals. Execute consistently.\n\n{company_name} works with {target_persona}s who are ready to commit.\n\n---\n\n*Interested? Let's talk.*",
            ],
        },
        "ad": {
            "professional": [
                f"**{topic} for {target_persona}s**\n\n✓ Practical Solutions\n✓ Expert Support from {company_name}\n✓ Results-Focused Approach\n\nLearn how we can help your business.\n\n[Learn More →]",
            ],
            "conversational": [
                f"Working on {topic.lower()}?\n\nYou're not alone. 🤝\n\n{company_name} helps {target_persona}s navigate these challenges.\n\nLet's chat - no pressure.\n\n[Book a Free Call]",
            ],
            "bold": [
                f"🚀 {topic.upper()}\n\nAchieve meaningful results.\n\n{company_name} helps {target_persona}s succeed.\n\n[Get Started →]",
            ],
        },
    }

    content_list = templates.get(content_type, {}).get(tone, templates["linkedin"]["professional"])
    results = []

    for i in range(variations):
        results.append(content_list[i % len(content_list)])

    return results


@router.post(
    "/{company_id}/campaigns/generate-content", response_model=list[GeneratedContentResponse]
)
async def generate_content(
    company_id: UUID,
    request: ContentGenerationRequest,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[GeneratedContentResponse]:
    """Generate marketing content using AI.

    Uses the Campaign Architect agent to generate content based on company context.
    Falls back to intelligent templates if AI generation fails.
    Content is persisted to the database for future reference.
    """
    await validate_company_access(company_id, current_user, db)
    company = await verify_company_exists(db, company_id)

    logger.info(
        "content_generation_requested",
        company_id=str(company_id),
        content_type=request.content_type,
        topic=request.topic,
        target_persona=request.target_persona,
    )

    now = datetime.utcnow()
    target_persona = request.target_persona or "Business Decision Makers"

    # Try AI generation first
    ai_content = await generate_content_with_ai(company, request)

    if ai_content:
        content_list = ai_content
        logger.info(
            "content_generated_with_ai", company_id=str(company_id), count=len(content_list)
        )
    else:
        # Fall back to templates with company context
        content_list = get_template_content(
            content_type=request.content_type,
            tone=request.tone,
            topic=request.topic,
            company_name=company.name,
            target_persona=target_persona,
            variations=request.variations,
        )
        logger.info(
            "content_generated_with_templates", company_id=str(company_id), count=len(content_list)
        )

    # Save to database and build response
    results = []
    for content in content_list:
        # Create database record
        db_content = GeneratedContentModel(
            company_id=company_id,
            content_type=request.content_type,
            content=content,
            tone=request.tone,
            target_persona=target_persona,
            topic=request.topic,
            key_points=request.key_points,
            include_cta=request.include_cta,
            created_at=now,
        )
        db.add(db_content)
        await db.flush()

        results.append(
            GeneratedContentResponse(
                id=str(db_content.id),
                content_type=request.content_type,
                content=content,
                tone=request.tone,
                target_persona=target_persona,
                created_at=now.isoformat(),
            )
        )

    await db.commit()

    logger.info("content_persisted", company_id=str(company_id), count=len(results))

    return results
