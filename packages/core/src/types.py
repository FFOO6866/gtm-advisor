"""GTM Advisor Type Definitions.

Domain-specific types for GTM advisory platform.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# Import SubscriptionTier from the single source of truth
from packages.database.src.models import SubscriptionTier

# =============================================================================
# Enums
# =============================================================================


class ExecutionMode(str, Enum):
    """Agent execution mode for different latency requirements."""

    STANDARD = "standard"  # Full PDCA with LLM calls (~1-2s)
    FAST = "fast"  # Single LLM call (~200-500ms)
    ULTRA_FAST = "ultra_fast"  # Rule-based only, no LLM (<10ms)


class AgentStatus(str, Enum):
    """Agent lifecycle status."""

    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    CHECKING = "checking"
    ADJUSTING = "adjusting"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConfidenceLevel(str, Enum):
    """Qualitative confidence levels."""

    LOW = "low"  # < 0.5
    MEDIUM = "medium"  # 0.5 - 0.7
    HIGH = "high"  # 0.7 - 0.85
    VERY_HIGH = "very_high"  # > 0.85


# NOTE: SubscriptionTier is defined in packages/database/src/models.py (single source of truth)
# Import with: from packages.database.src.models import SubscriptionTier
# Values: FREE, TIER1, TIER2


class PDCAPhase(str, Enum):
    """PDCA cycle phase."""

    PLAN = "plan"
    DO = "do"
    CHECK = "check"
    ACT = "act"


class LeadStatus(str, Enum):
    """Lead qualification status."""

    NEW = "new"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    CONVERTED = "converted"


class IndustryVertical(str, Enum):
    """Target industry verticals."""

    FINTECH = "fintech"
    SAAS = "saas"
    ECOMMERCE = "ecommerce"
    HEALTHTECH = "healthtech"
    EDTECH = "edtech"
    PROPTECH = "proptech"
    LOGISTICS = "logistics"
    MANUFACTURING = "manufacturing"
    PROFESSIONAL_SERVICES = "professional_services"
    OTHER = "other"


class CompanyStage(str, Enum):
    """Company growth stage."""

    PRE_SEED = "pre_seed"
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    SERIES_C_PLUS = "series_c_plus"
    GROWTH = "growth"
    MATURE = "mature"


# =============================================================================
# PDCA Types
# =============================================================================


class PDCAState(BaseModel):
    """State tracking for PDCA execution cycle."""

    phase: PDCAPhase = Field(default=PDCAPhase.PLAN)
    iteration: int = Field(default=0, ge=0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)
    plan: dict[str, Any] | None = Field(default=None)
    result: dict[str, Any] | None = Field(default=None)
    adjustments: list[str] = Field(default_factory=list)
    error: str | None = Field(default=None)


class FastPathRule(BaseModel):
    """Rule for ultra-fast execution path."""

    name: str = Field(..., description="Rule identifier")
    conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="Conditions to match (key: value or tuple for ranges)",
    )
    output: dict[str, Any] = Field(..., description="Output when rule matches")
    priority: int = Field(default=0, description="Higher priority rules evaluated first")


class FastPathConfig(BaseModel):
    """Configuration for fast/ultra-fast execution modes."""

    enabled: bool = Field(default=False)
    rules: list[FastPathRule] = Field(default_factory=list)
    fallback_to_standard: bool = Field(
        default=True,
        description="Fall back to STANDARD mode if no rules match",
    )


# =============================================================================
# Domain Types - Company & User
# =============================================================================


class CompanyProfile(BaseModel):
    """Company profile for GTM analysis."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    website: str | None = Field(default=None)
    industry: IndustryVertical = Field(default=IndustryVertical.OTHER)
    stage: CompanyStage = Field(default=CompanyStage.SEED)

    # Location
    country: str = Field(default="Singapore")
    city: str | None = Field(default=None)

    # Business Details
    founded_year: int | None = Field(default=None)
    employee_count: int | None = Field(default=None, ge=1)
    annual_revenue_sgd: float | None = Field(default=None, ge=0)
    funding_raised_sgd: float | None = Field(default=None, ge=0)

    # Products/Services
    products: list[str] = Field(default_factory=list)
    target_markets: list[str] = Field(default_factory=list)
    value_proposition: str | None = Field(default=None)

    # GTM Context
    current_challenges: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserProfile(BaseModel):
    """User profile for the platform."""

    id: UUID = Field(default_factory=uuid4)
    email: str = Field(...)
    name: str = Field(...)
    company_id: UUID | None = Field(default=None)
    role: str = Field(default="founder")
    tier: SubscriptionTier = Field(default=SubscriptionTier.FREE)

    # Usage tracking
    daily_requests: int = Field(default=0, ge=0)
    total_requests: int = Field(default=0, ge=0)
    last_request_at: datetime | None = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Domain Types - Leads & Campaigns
# =============================================================================


class LeadProfile(BaseModel):
    """Potential lead/prospect profile."""

    id: UUID = Field(default_factory=uuid4)
    company_name: str = Field(...)
    contact_name: str | None = Field(default=None)
    contact_title: str | None = Field(default=None)
    contact_email: str | None = Field(default=None)
    contact_linkedin: str | None = Field(default=None)

    # Company Info
    industry: IndustryVertical = Field(default=IndustryVertical.OTHER)
    employee_count: int | None = Field(default=None)
    location: str | None = Field(default=None)
    website: str | None = Field(default=None)

    # Lead Scoring
    status: LeadStatus = Field(default=LeadStatus.NEW)
    fit_score: float = Field(default=0.0, ge=0.0, le=1.0)
    intent_score: float = Field(default=0.0, ge=0.0, le=1.0)
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Context
    pain_points: list[str] = Field(default_factory=list)
    trigger_events: list[str] = Field(default_factory=list)
    recommended_approach: str | None = Field(default=None)

    # Source
    source: str = Field(default="platform")
    source_url: str | None = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class CampaignBrief(BaseModel):
    """Marketing/outreach campaign brief."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(...)
    objective: str = Field(...)

    # Target
    target_persona: str | None = Field(default=None)
    target_industries: list[IndustryVertical] = Field(default_factory=list)
    target_company_size: str | None = Field(default=None)
    target_geography: list[str] = Field(default_factory=list)

    # Messaging
    key_messages: list[str] = Field(default_factory=list)
    value_propositions: list[str] = Field(default_factory=list)
    call_to_action: str | None = Field(default=None)

    # Channels
    channels: list[str] = Field(default_factory=list)
    budget_sgd: float | None = Field(default=None)

    # Content
    content_ideas: list[str] = Field(default_factory=list)
    email_templates: list[str] = Field(default_factory=list)
    linkedin_posts: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Domain Types - Insights & Analysis
# =============================================================================


class MarketInsight(BaseModel):
    """Market research insight."""

    id: UUID = Field(default_factory=uuid4)
    title: str = Field(...)
    summary: str = Field(...)
    category: str = Field(default="general")  # trend, opportunity, threat, news

    # Details
    key_findings: list[str] = Field(default_factory=list)
    implications: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    # Sources
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # Relevance
    relevant_industries: list[IndustryVertical] = Field(default_factory=list)
    relevant_to_company: bool = Field(default=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class CompetitorAnalysis(BaseModel):
    """Competitor analysis result."""

    id: UUID = Field(default_factory=uuid4)
    competitor_name: str = Field(...)
    website: str | None = Field(default=None)

    # Profile
    description: str = Field(default="")
    founded_year: int | None = Field(default=None)
    employee_count: int | None = Field(default=None)
    funding_raised: float | None = Field(default=None)
    headquarters: str | None = Field(default=None)

    # Analysis
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)

    # Products
    products: list[str] = Field(default_factory=list)
    pricing_model: str | None = Field(default=None)
    target_market: str | None = Field(default=None)

    # Positioning
    positioning: str | None = Field(default=None)
    key_differentiators: list[str] = Field(default_factory=list)
    market_share_estimate: str | None = Field(default=None)

    # Intelligence
    recent_news: list[str] = Field(default_factory=list)
    strategic_moves: list[str] = Field(default_factory=list)

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CustomerPersona(BaseModel):
    """Ideal customer persona."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(...)  # e.g., "Tech-Savvy Startup Founder"
    role: str = Field(...)  # e.g., "CEO", "CTO", "VP Sales"

    # Demographics
    age_range: str | None = Field(default=None)
    experience_level: str | None = Field(default=None)
    education: str | None = Field(default=None)

    # Company Context
    company_size: str | None = Field(default=None)
    company_stage: CompanyStage | None = Field(default=None)
    industries: list[IndustryVertical] = Field(default_factory=list)

    # Psychographics
    goals: list[str] = Field(default_factory=list)
    challenges: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    motivations: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)

    # Behavior
    information_sources: list[str] = Field(default_factory=list)
    decision_criteria: list[str] = Field(default_factory=list)
    buying_process: str | None = Field(default=None)

    # Engagement
    preferred_channels: list[str] = Field(default_factory=list)
    content_preferences: list[str] = Field(default_factory=list)
    messaging_tone: str | None = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Agent Communication Types
# =============================================================================


class AgentTask(BaseModel):
    """Task assigned to an agent."""

    id: UUID = Field(default_factory=uuid4)
    agent_name: str = Field(...)
    task_type: str = Field(...)
    input_data: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    result: dict[str, Any] | None = Field(default=None)
    error: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)


class AgentMessage(BaseModel):
    """Message between agents."""

    id: UUID = Field(default_factory=uuid4)
    from_agent: str = Field(...)
    to_agent: str = Field(...)
    message_type: str = Field(...)  # request, response, notification
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: UUID | None = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# API Response Types
# =============================================================================


class GTMAnalysisResult(BaseModel):
    """Complete GTM analysis result."""

    id: UUID = Field(default_factory=uuid4)
    company_id: UUID = Field(...)

    # Analysis Components
    market_insights: list[MarketInsight] = Field(default_factory=list)
    competitor_analysis: list[CompetitorAnalysis] = Field(default_factory=list)
    customer_personas: list[CustomerPersona] = Field(default_factory=list)
    leads: list[LeadProfile] = Field(default_factory=list)
    campaign_brief: CampaignBrief | None = Field(default=None)

    # Summary
    executive_summary: str = Field(default="")
    key_recommendations: list[str] = Field(default_factory=list)

    # Metadata
    agents_used: list[str] = Field(default_factory=list)
    total_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    processing_time_seconds: float = Field(default=0.0)

    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Helper Functions
# =============================================================================


def confidence_to_level(confidence: float) -> ConfidenceLevel:
    """Convert numeric confidence to qualitative level."""
    if confidence < 0.5:
        return ConfidenceLevel.LOW
    elif confidence < 0.7:
        return ConfidenceLevel.MEDIUM
    elif confidence < 0.85:
        return ConfidenceLevel.HIGH
    else:
        return ConfidenceLevel.VERY_HIGH
