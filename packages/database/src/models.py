"""SQLAlchemy models for GTM Advisor.

Tables:
- users: User accounts with subscription tiers
- companies: Company profiles for analysis
- analyses: GTM analysis results
- consents: PDPA consent records
- audit_logs: Audit trail for compliance
- competitors: Tracked competitors
- icps: Ideal Customer Profiles
- personas: Buyer personas
- leads: Generated leads
- campaigns: Campaign briefs and content
- market_insights: Market intelligence data
- workforce_configs: Digital Workforce configurations
- execution_runs: Workforce execution cycles
- execution_metrics: KPI snapshots per execution run
- sg_knowledge_articles: Singapore government reference data (grants, regulations, enforcement)
"""

import uuid
from datetime import UTC, datetime
from enum import Enum as PyEnum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class SubscriptionTier(str, PyEnum):
    """User subscription tiers."""

    FREE = "free"
    TIER1 = "tier1"  # $700/month
    TIER2 = "tier2"  # $7,000/month


class AnalysisStatus(str, PyEnum):
    """Analysis execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConsentPurpose(str, PyEnum):
    """PDPA consent purposes."""

    MARKETING = "marketing"
    SALES = "sales"
    ANALYTICS = "analytics"
    PROFILING = "profiling"
    THIRD_PARTY = "third_party"


class ThreatLevel(str, PyEnum):
    """Competitor threat level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LeadStatus(str, PyEnum):
    """Lead qualification status."""

    NEW = "new"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    CONVERTED = "converted"
    LOST = "lost"


class CampaignStatus(str, PyEnum):
    """Campaign status."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    company_name = Column(String(200))

    # Subscription
    tier = Column(Enum(SubscriptionTier), default=SubscriptionTier.FREE, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Usage tracking
    daily_requests = Column(Integer, default=0)
    last_request_date = Column(DateTime)

    # User preferences
    preferences = Column(JSON, default=dict)  # UI settings, notifications, etc.

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    companies = relationship("Company", back_populates="owner")
    analyses = relationship("Analysis", back_populates="user")

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Company(Base):
    """Company profile for GTM analysis."""

    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Nullable for MVP

    # Basic info
    name = Column(String(200), nullable=False)
    website = Column(String(255))
    description = Column(Text)
    industry = Column(String(100))

    # Enriched data (from Company Enricher agent)
    founded_year = Column(String(10))
    headquarters = Column(String(200))
    employee_count = Column(String(50))
    funding_stage = Column(String(100))
    tech_stack = Column(JSON, default=list)
    products = Column(JSON, default=list)  # List of product objects

    # GTM context
    goals = Column(JSON, default=list)  # List of goals
    challenges = Column(JSON, default=list)  # List of challenges
    competitors = Column(JSON, default=list)  # List of competitor names
    target_markets = Column(JSON, default=list)  # List of markets
    value_proposition = Column(Text)

    # Persistent context sources — uploaded docs, website scrapes, etc.
    # List of {type, name, text, chars, added_at} dicts.
    # Agents receive all sources joined into a single additional_context string.
    context_sources = Column(JSON, nullable=True, default=list)

    # Enrichment metadata
    enrichment_confidence = Column(Float, default=0.0)
    last_enriched_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    owner = relationship("User", back_populates="companies")
    analyses = relationship("Analysis", back_populates="company")
    tracked_competitors = relationship("Competitor", back_populates="company")
    icps = relationship("ICP", back_populates="company")
    leads = relationship("Lead", back_populates="company")
    campaigns = relationship("Campaign", back_populates="company")
    market_insights = relationship("MarketInsight", back_populates="company")

    __table_args__ = (Index("ix_companies_owner_id", "owner_id"),)

    def __repr__(self) -> str:
        return f"<Company {self.name}>"


class Analysis(Base):
    """GTM analysis result."""

    __tablename__ = "analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )  # Nullable for MVP unauthenticated access
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    # Status
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING, nullable=False)
    progress = Column(Integer, default=0)  # 0-100
    current_agent = Column(String(50))
    completed_agents = Column(JSON, default=list)
    error = Column(Text)

    # Results (stored as JSON)
    executive_summary = Column(Text)
    key_recommendations = Column(JSON, default=list)
    market_insights = Column(JSON, default=list)
    competitor_analysis = Column(JSON, default=list)
    customer_personas = Column(JSON, default=list)
    leads = Column(JSON, default=list)
    campaign_brief = Column(JSON)

    # Metrics
    total_confidence = Column(Float, default=0.0)
    processing_time_seconds = Column(Float, default=0.0)
    agents_used = Column(JSON, default=list)

    # Decision attribution
    algorithm_decisions = Column(Integer, default=0)
    llm_decisions = Column(Integer, default=0)
    tool_calls = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    completed_at = Column(DateTime)

    # Relationships
    user = relationship("User", back_populates="analyses")
    company = relationship("Company", back_populates="analyses")

    __table_args__ = (
        Index("ix_analyses_user_id", "user_id"),
        Index("ix_analyses_company_id", "company_id"),
        Index("ix_analyses_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Analysis {self.id} ({self.status.value})>"


class Competitor(Base):
    """Tracked competitor for competitive intelligence."""

    __tablename__ = "competitors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    # Basic info
    name = Column(String(200), nullable=False)
    website = Column(String(255))
    description = Column(Text)

    # SWOT Analysis
    strengths = Column(JSON, default=list)  # List of strings
    weaknesses = Column(JSON, default=list)
    opportunities = Column(JSON, default=list)
    threats = Column(JSON, default=list)

    # Competitive positioning
    threat_level = Column(Enum(ThreatLevel), default=ThreatLevel.MEDIUM)
    positioning = Column(Text)  # Their market positioning
    pricing_info = Column(JSON)  # Pricing tiers if known

    # Battle card data
    our_advantages = Column(JSON, default=list)
    their_advantages = Column(JSON, default=list)
    key_objection_handlers = Column(JSON, default=list)

    # Tracking
    is_active = Column(Boolean, default=True)
    last_updated = Column(DateTime, default=lambda: datetime.now(UTC))

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    company = relationship("Company", back_populates="tracked_competitors")
    tracking_alerts = relationship("CompetitorAlert", back_populates="competitor")

    __table_args__ = (
        Index("ix_competitors_company_id", "company_id"),
        Index("ix_competitors_threat_level", "threat_level"),
    )

    def __repr__(self) -> str:
        return f"<Competitor {self.name}>"


class CompetitorAlert(Base):
    """Alerts for competitor changes."""

    __tablename__ = "competitor_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    competitor_id = Column(UUID(as_uuid=True), ForeignKey("competitors.id"), nullable=False)

    # Alert details
    alert_type = Column(String(50), nullable=False)  # pricing_change, news, job_posting, etc.
    severity = Column(String(20), default="medium")  # low, medium, high
    title = Column(String(200), nullable=False)
    description = Column(Text)
    source_url = Column(String(500))

    # Status
    is_read = Column(Boolean, default=False)
    is_dismissed = Column(Boolean, default=False)

    # Timestamps
    detected_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    read_at = Column(DateTime)

    # Relationships
    competitor = relationship("Competitor", back_populates="tracking_alerts")

    __table_args__ = (
        Index("ix_competitor_alerts_competitor_id", "competitor_id"),
        Index("ix_competitor_alerts_is_read", "is_read"),
    )


class ICP(Base):
    """Ideal Customer Profile."""

    __tablename__ = "icps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    # Profile basics
    name = Column(String(200), nullable=False)  # e.g., "Growth-Stage SaaS"
    description = Column(Text)
    fit_score = Column(Integer, default=0)  # 0-100

    # Characteristics
    company_size = Column(String(100))  # e.g., "20-100 employees"
    revenue_range = Column(String(100))  # e.g., "SGD 2-10M ARR"
    industry = Column(String(100))
    tech_stack = Column(String(200))
    buying_triggers = Column(JSON, default=list)  # Events that trigger buying

    # Pain points and needs
    pain_points = Column(JSON, default=list)
    needs = Column(JSON, default=list)

    # Matching companies count (cached)
    matching_companies_count = Column(Integer, default=0)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    company = relationship("Company", back_populates="icps")
    personas = relationship("Persona", back_populates="icp")

    __table_args__ = (Index("ix_icps_company_id", "company_id"),)

    def __repr__(self) -> str:
        return f"<ICP {self.name}>"


class Persona(Base):
    """Buyer persona within an ICP."""

    __tablename__ = "personas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    icp_id = Column(UUID(as_uuid=True), ForeignKey("icps.id"), nullable=False)

    # Basic info
    name = Column(String(100), nullable=False)  # e.g., "Marketing Michelle"
    role = Column(String(100), nullable=False)  # e.g., "Head of Marketing"
    avatar = Column(String(10))  # Emoji or icon identifier

    # Demographics
    age_range = Column(String(20))
    experience_years = Column(String(20))
    education = Column(String(100))

    # Psychographics
    goals = Column(JSON, default=list)
    challenges = Column(JSON, default=list)
    objections = Column(JSON, default=list)

    # Engagement
    preferred_channels = Column(JSON, default=list)  # LinkedIn, Email, etc.
    messaging_hooks = Column(JSON, default=list)  # What resonates with them
    content_preferences = Column(JSON, default=list)  # Blog, webinar, etc.

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    icp = relationship("ICP", back_populates="personas")

    __table_args__ = (Index("ix_personas_icp_id", "icp_id"),)

    def __repr__(self) -> str:
        return f"<Persona {self.name} ({self.role})>"


class Lead(Base):
    """Generated lead / prospect."""

    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    icp_id = Column(UUID(as_uuid=True), ForeignKey("icps.id"))

    # Lead company info
    lead_company_name = Column(String(200), nullable=False)
    lead_company_website = Column(String(255))
    lead_company_industry = Column(String(100))
    lead_company_size = Column(String(50))
    lead_company_description = Column(Text)

    # Contact info (if available)
    contact_name = Column(String(100))
    contact_title = Column(String(100))
    contact_email = Column(String(255))
    contact_linkedin = Column(String(255))

    # Scoring
    fit_score = Column(Integer, default=0)  # 0-100, how well they match ICP
    intent_score = Column(Integer, default=0)  # 0-100, buying intent signals
    overall_score = Column(Integer, default=0)  # Combined score

    # Qualification
    status = Column(Enum(LeadStatus), default=LeadStatus.NEW)
    qualification_reasons = Column(JSON, default=list)  # Why they're a good fit
    disqualification_reasons = Column(JSON, default=list)

    # Source
    source = Column(String(100))  # How the lead was found
    source_url = Column(String(500))

    # Engagement
    notes = Column(Text)
    tags = Column(JSON, default=list)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    contacted_at = Column(DateTime)
    converted_at = Column(DateTime)

    # Relationships
    company = relationship("Company", back_populates="leads")

    __table_args__ = (
        Index("ix_leads_company_id", "company_id"),
        Index("ix_leads_status", "status"),
        Index("ix_leads_overall_score", "overall_score"),
    )

    def __repr__(self) -> str:
        return f"<Lead {self.lead_company_name}>"


class Campaign(Base):
    """Marketing campaign brief and content."""

    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    icp_id = Column(UUID(as_uuid=True), ForeignKey("icps.id"))

    # Campaign basics
    name = Column(String(200), nullable=False)
    description = Column(Text)
    objective = Column(String(100))  # awareness, lead_gen, conversion, etc.
    status = Column(Enum(CampaignStatus), default=CampaignStatus.DRAFT)

    # Target audience
    target_personas = Column(JSON, default=list)  # List of persona IDs
    target_industries = Column(JSON, default=list)
    target_company_sizes = Column(JSON, default=list)

    # Messaging
    key_messages = Column(JSON, default=list)
    value_propositions = Column(JSON, default=list)
    call_to_action = Column(String(200))

    # Channels
    channels = Column(JSON, default=list)  # email, linkedin, content, etc.

    # Content assets
    email_templates = Column(JSON, default=list)  # List of email template objects
    linkedin_posts = Column(JSON, default=list)
    ad_copy = Column(JSON, default=list)
    landing_page_copy = Column(JSON)
    blog_outlines = Column(JSON, default=list)

    # Budget and timeline
    budget = Column(Float)
    currency = Column(String(3), default="SGD")
    start_date = Column(DateTime)
    end_date = Column(DateTime)

    # Performance (for tracking)
    metrics = Column(JSON, default=dict)  # impressions, clicks, leads, etc.

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    company = relationship("Company", back_populates="campaigns")

    __table_args__ = (
        Index("ix_campaigns_company_id", "company_id"),
        Index("ix_campaigns_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Campaign {self.name}>"


class MarketInsight(Base):
    """Market intelligence insights."""

    __tablename__ = "market_insights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    # Insight details
    insight_type = Column(String(50), nullable=False)  # trend, opportunity, threat, news
    category = Column(String(100))  # market, competitor, technology, regulation
    title = Column(String(300), nullable=False)
    summary = Column(Text)
    full_content = Column(Text)

    # Impact assessment
    impact_level = Column(String(20))  # low, medium, high
    relevance_score = Column(Float, default=0.0)  # 0-1

    # Source
    source_name = Column(String(200))
    source_url = Column(String(500))
    published_at = Column(DateTime)

    # Actionability
    recommended_actions = Column(JSON, default=list)
    related_agents = Column(JSON, default=list)  # Which agents should act on this

    # Status
    is_read = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    expires_at = Column(DateTime)  # When insight becomes stale

    # Relationships
    company = relationship("Company", back_populates="market_insights")

    __table_args__ = (
        Index("ix_market_insights_company_id", "company_id"),
        Index("ix_market_insights_type", "insight_type"),
        Index("ix_market_insights_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<MarketInsight {self.title[:50]}>"


class Consent(Base):
    """PDPA consent record."""

    __tablename__ = "consents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Subject identification (hashed for privacy)
    data_subject_id = Column(String(64), nullable=False, index=True)  # SHA256 hash of identifier

    # Consent details
    purpose = Column(Enum(ConsentPurpose), nullable=False)
    granted = Column(Boolean, nullable=False)
    source = Column(String(100))  # Where consent was collected
    ip_address = Column(String(45))  # IPv4 or IPv6

    # Validity
    granted_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    expires_at = Column(DateTime)
    revoked_at = Column(DateTime)

    __table_args__ = (
        Index("ix_consents_user_id", "user_id"),
        Index("ix_consents_data_subject_purpose", "data_subject_id", "purpose"),
    )

    def __repr__(self) -> str:
        return f"<Consent {self.purpose.value} granted={self.granted}>"


class AuditLog(Base):
    """Audit log for compliance and debugging."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Event details
    event_type = Column(String(50), nullable=False, index=True)
    event_subtype = Column(String(50))
    agent_id = Column(String(50), index=True)
    session_id = Column(UUID(as_uuid=True), index=True)

    # Context
    resource_type = Column(String(50))  # e.g., "company", "lead", "analysis"
    resource_id = Column(String(100))
    action = Column(String(50))  # e.g., "create", "read", "update", "delete"

    # Details
    details = Column(JSON)  # Flexible storage for event-specific data
    extra_data = Column(JSON)  # Additional context (renamed from 'metadata' - reserved)

    # Result
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    duration_ms = Column(Float)

    # Timestamps
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True)

    __table_args__ = (
        Index("ix_audit_logs_user_event", "user_id", "event_type"),
        Index("ix_audit_logs_timestamp_event", "timestamp", "event_type"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.event_type} at {self.timestamp}>"


# ============================================================================
# Strategy Models
# ============================================================================


class RecommendationStatus(str, PyEnum):
    """Strategy recommendation status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


class RecommendationPriority(str, PyEnum):
    """Strategy recommendation priority."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PhaseStatus(str, PyEnum):
    """Strategy phase status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


class StrategyRun(Base):
    """Strategy analysis run."""

    __tablename__ = "strategy_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    # Status
    status = Column(String(20), default="running")  # running, completed, failed

    # Metrics
    agents_active = Column(Integer, default=0)
    agents_total = Column(Integer, default=6)
    tasks_completed = Column(Integer, default=0)
    avg_confidence = Column(Float, default=0.0)
    execution_time_ms = Column(Float, default=0.0)

    # Timestamps
    started_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    completed_at = Column(DateTime)

    # Relationships
    phases = relationship(
        "StrategyPhase", back_populates="strategy_run", cascade="all, delete-orphan"
    )
    recommendations = relationship(
        "StrategyRecommendation", back_populates="strategy_run", cascade="all, delete-orphan"
    )
    activities = relationship(
        "AgentActivity", back_populates="strategy_run", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_strategy_runs_company_id", "company_id"),)


class StrategyPhase(Base):
    """Strategy phase tracking."""

    __tablename__ = "strategy_phases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    strategy_run_id = Column(UUID(as_uuid=True), ForeignKey("strategy_runs.id"), nullable=False)

    # Phase info
    phase_key = Column(String(50), nullable=False)  # discovery, analysis, strategy, etc.
    name = Column(String(100), nullable=False)
    status = Column(Enum(PhaseStatus), default=PhaseStatus.PENDING)
    icon = Column(String(10))

    # Timestamps
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Relationships
    strategy_run = relationship("StrategyRun", back_populates="phases")

    __table_args__ = (Index("ix_strategy_phases_run_id", "strategy_run_id"),)


class StrategyRecommendation(Base):
    """Strategy recommendation."""

    __tablename__ = "strategy_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    strategy_run_id = Column(UUID(as_uuid=True), ForeignKey("strategy_runs.id"))

    # Recommendation details
    priority = Column(Enum(RecommendationPriority), default=RecommendationPriority.MEDIUM)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    source_agents = Column(JSON, default=list)  # List of agent IDs
    impact = Column(String(200))
    confidence = Column(Float, default=0.0)
    status = Column(Enum(RecommendationStatus), default=RecommendationStatus.PENDING)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    strategy_run = relationship("StrategyRun", back_populates="recommendations")

    __table_args__ = (
        Index("ix_strategy_recommendations_company_id", "company_id"),
        Index("ix_strategy_recommendations_status", "status"),
    )


class AgentActivity(Base):
    """Agent activity log."""

    __tablename__ = "agent_activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    strategy_run_id = Column(UUID(as_uuid=True), ForeignKey("strategy_runs.id"))
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    # Activity details
    agent_id = Column(String(50), nullable=False)
    agent_name = Column(String(100), nullable=False)
    action = Column(String(300), nullable=False)
    icon = Column(String(10))

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    strategy_run = relationship("StrategyRun", back_populates="activities")

    __table_args__ = (
        Index("ix_agent_activities_company_id", "company_id"),
        Index("ix_agent_activities_created_at", "created_at"),
    )


# ============================================================================
# Agent Run Models
# ============================================================================


class AgentRunStatus(str, PyEnum):
    """Agent run status."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class AgentRun(Base):
    """Agent execution run."""

    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    # Agent info
    agent_id = Column(String(50), nullable=False)
    task_id = Column(UUID(as_uuid=True), default=uuid4, nullable=False)

    # Status
    status = Column(Enum(AgentRunStatus), default=AgentRunStatus.RUNNING)
    error_message = Column(Text)

    # Results
    confidence = Column(Float)
    result_summary = Column(Text)

    # Timestamps
    started_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    completed_at = Column(DateTime)

    __table_args__ = (
        Index("ix_agent_runs_company_id", "company_id"),
        Index("ix_agent_runs_agent_id", "agent_id"),
        Index("ix_agent_runs_company_agent", "company_id", "agent_id"),
    )


# ============================================================================
# Generated Content Models
# ============================================================================


class GeneratedContent(Base):
    """AI-generated marketing content."""

    __tablename__ = "generated_content"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"))

    # Content details
    content_type = Column(String(20), nullable=False)  # linkedin, email, blog, ad
    content = Column(Text, nullable=False)
    tone = Column(String(20))  # professional, conversational, bold
    target_persona = Column(String(100))
    topic = Column(String(300))

    # Metadata
    key_points = Column(JSON, default=list)
    include_cta = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        Index("ix_generated_content_company_id", "company_id"),
        Index("ix_generated_content_type", "content_type"),
    )


# ============================================================================
# Knowledge Web Models - Evidence-Backed Intelligence Graph
# ============================================================================


class SourceType(str, PyEnum):
    """Source types for evidenced facts."""

    ACRA = "acra"  # Singapore company registry
    EODHD = "eodhd"  # Financial data
    NEWSAPI = "newsapi"  # News articles
    PERPLEXITY = "perplexity"  # Web research
    WEB_SCRAPE = "web_scrape"  # Direct website scraping
    LINKEDIN = "linkedin"  # LinkedIn public data
    JOB_BOARD = "job_board"  # Job postings
    GOVERNMENT = "government"  # Government data (MAS, GeBIZ, etc.)
    REVIEW_SITE = "review_site"  # G2, Capterra, etc.
    PRESS_RELEASE = "press_release"  # Company press releases
    SEC_FILING = "sec_filing"  # Regulatory filings
    USER_INPUT = "user_input"  # User-provided information


class FactType(str, PyEnum):
    """Types of evidenced facts."""

    COMPANY_INFO = "company_info"  # Basic company data
    FUNDING = "funding"  # Funding rounds, investors
    EXECUTIVE = "executive"  # Executive appointments, departures
    PRODUCT = "product"  # Product launches, updates
    PARTNERSHIP = "partnership"  # Business partnerships
    EXPANSION = "expansion"  # Market expansion, new offices
    HIRING = "hiring"  # Hiring activity, job postings
    TECHNOLOGY = "technology"  # Tech stack, tools used
    FINANCIAL = "financial"  # Revenue, growth metrics
    MARKET_TREND = "market_trend"  # Industry trends
    COMPETITOR_MOVE = "competitor_move"  # Competitor activities
    REGULATION = "regulation"  # Regulatory changes
    ACQUISITION = "acquisition"  # M&A activity
    SENTIMENT = "sentiment"  # Reviews, public perception


class EntityType(str, PyEnum):
    """Types of entities in the knowledge graph."""

    COMPANY = "company"
    PERSON = "person"
    PRODUCT = "product"
    INVESTOR = "investor"
    INDUSTRY = "industry"
    TECHNOLOGY = "technology"
    LOCATION = "location"


class RelationType(str, PyEnum):
    """Types of relationships between entities."""

    WORKS_AT = "works_at"
    FOUNDED = "founded"
    INVESTED_IN = "invested_in"
    COMPETES_WITH = "competes_with"
    PARTNERS_WITH = "partners_with"
    ACQUIRED = "acquired"
    USES_TECHNOLOGY = "uses_technology"
    OPERATES_IN = "operates_in"
    SUPPLIES_TO = "supplies_to"
    FORMER_EMPLOYEE = "former_employee"


class EvidencedFact(Base):
    """Core fact storage with full provenance tracking.

    Every fact has a source URL, timestamp, and confidence score.
    This is the foundation of the Knowledge Web - no fact without evidence.
    """

    __tablename__ = "evidenced_facts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # The actual claim/fact
    claim = Column(Text, nullable=False)
    fact_type = Column(Enum(FactType), nullable=False)

    # Source provenance (REQUIRED - no fact without source)
    source_type = Column(Enum(SourceType), nullable=False)
    source_name = Column(String(200), nullable=False)  # e.g., "TechCrunch", "ACRA"
    source_url = Column(String(1000))  # URL to original source
    raw_excerpt = Column(Text)  # Original text from source

    # Temporal context
    published_at = Column(DateTime)  # When the source was published
    captured_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    valid_from = Column(DateTime)  # When fact became true
    valid_until = Column(DateTime)  # When fact stopped being true (if known)

    # Confidence scoring
    confidence = Column(Float, default=0.8, nullable=False)  # 0-1 confidence
    verification_count = Column(Integer, default=1)  # How many sources confirm this

    # Structured data extraction (optional)
    extracted_data = Column(JSON, default=dict)  # Key-value pairs from the fact

    # Processing metadata
    mcp_server = Column(String(50))  # Which MCP server provided this
    processing_model = Column(String(50))  # LLM used for extraction
    is_verified = Column(Boolean, default=False)  # Human verified
    is_stale = Column(Boolean, default=False)  # Marked as outdated

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    entity_links = relationship(
        "FactEntityLink", back_populates="fact", cascade="all, delete-orphan"
    )
    relation_links = relationship(
        "FactRelationLink", back_populates="fact", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_evidenced_facts_fact_type", "fact_type"),
        Index("ix_evidenced_facts_source_type", "source_type"),
        Index("ix_evidenced_facts_captured_at", "captured_at"),
        Index("ix_evidenced_facts_confidence", "confidence"),
        Index("ix_evidenced_facts_source_type_captured", "source_type", "captured_at"),
    )

    def __repr__(self) -> str:
        return f"<EvidencedFact {self.fact_type.value}: {self.claim[:50]}...>"


class Entity(Base):
    """Entities in the knowledge graph (companies, people, products, etc.)."""

    __tablename__ = "entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Entity identification
    entity_type = Column(Enum(EntityType), nullable=False)
    name = Column(String(300), nullable=False)
    canonical_name = Column(String(300))  # Normalized version for matching

    # External identifiers
    acra_uen = Column(String(20), unique=True)  # Singapore UEN
    linkedin_url = Column(String(500))
    website = Column(String(500))
    external_ids = Column(JSON, default=dict)  # Other IDs (crunchbase, etc.)

    # Entity metadata
    description = Column(Text)
    attributes = Column(JSON, default=dict)  # Flexible key-value attributes

    # Confidence and freshness
    confidence = Column(Float, default=0.8)
    last_updated = Column(DateTime, default=lambda: datetime.now(UTC))
    fact_count = Column(Integer, default=0)  # Number of facts about this entity

    # Status
    is_active = Column(Boolean, default=True)
    merged_into_id = Column(UUID(as_uuid=True))  # If entity was merged/deduplicated

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    fact_links = relationship(
        "FactEntityLink", back_populates="entity", cascade="all, delete-orphan"
    )
    outgoing_relations = relationship(
        "EntityRelation",
        foreign_keys="EntityRelation.source_entity_id",
        back_populates="source_entity",
        cascade="all, delete-orphan",
    )
    incoming_relations = relationship(
        "EntityRelation",
        foreign_keys="EntityRelation.target_entity_id",
        back_populates="target_entity",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_entities_entity_type", "entity_type"),
        Index("ix_entities_name", "name"),
        Index("ix_entities_canonical_name", "canonical_name"),
        Index("ix_entities_acra_uen", "acra_uen"),
        Index("ix_entities_type_name", "entity_type", "name"),
    )

    def __repr__(self) -> str:
        return f"<Entity {self.entity_type.value}: {self.name}>"


class EntityRelation(Base):
    """Relationships between entities in the knowledge graph."""

    __tablename__ = "entity_relations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Relationship endpoints
    source_entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    target_entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    relation_type = Column(Enum(RelationType), nullable=False)

    # Relationship metadata
    attributes = Column(JSON, default=dict)  # Role, title, dates, etc.
    confidence = Column(Float, default=0.8)

    # Temporal validity
    valid_from = Column(DateTime)
    valid_until = Column(DateTime)
    is_current = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    source_entity = relationship(
        "Entity", foreign_keys=[source_entity_id], back_populates="outgoing_relations"
    )
    target_entity = relationship(
        "Entity", foreign_keys=[target_entity_id], back_populates="incoming_relations"
    )
    fact_links = relationship(
        "FactRelationLink", back_populates="relation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_entity_relations_source", "source_entity_id"),
        Index("ix_entity_relations_target", "target_entity_id"),
        Index("ix_entity_relations_type", "relation_type"),
        Index(
            "ix_entity_relations_source_target",
            "source_entity_id",
            "target_entity_id",
            "relation_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<EntityRelation {self.relation_type.value}>"


class FactEntityLink(Base):
    """Links facts to entities they describe."""

    __tablename__ = "fact_entity_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    fact_id = Column(UUID(as_uuid=True), ForeignKey("evidenced_facts.id"), nullable=False)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)

    # Link metadata
    role = Column(String(50))  # e.g., "subject", "object", "mentioned"
    relevance = Column(Float, default=1.0)  # How relevant the fact is to the entity

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    fact = relationship("EvidencedFact", back_populates="entity_links")
    entity = relationship("Entity", back_populates="fact_links")

    __table_args__ = (
        Index("ix_fact_entity_links_fact", "fact_id"),
        Index("ix_fact_entity_links_entity", "entity_id"),
        Index("ix_fact_entity_links_fact_entity", "fact_id", "entity_id", unique=True),
    )


class FactRelationLink(Base):
    """Links facts to entity relations they describe."""

    __tablename__ = "fact_relation_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    fact_id = Column(UUID(as_uuid=True), ForeignKey("evidenced_facts.id"), nullable=False)
    relation_id = Column(
        UUID(as_uuid=True), ForeignKey("entity_relations.id"), nullable=False
    )

    # Link metadata
    is_primary_evidence = Column(Boolean, default=False)  # Is this the main evidence?

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    fact = relationship("EvidencedFact", back_populates="relation_links")
    relation = relationship("EntityRelation", back_populates="fact_links")

    __table_args__ = (
        Index("ix_fact_relation_links_fact", "fact_id"),
        Index("ix_fact_relation_links_relation", "relation_id"),
        Index(
            "ix_fact_relation_links_fact_relation", "fact_id", "relation_id", unique=True
        ),
    )


class LeadJustification(Base):
    """Evidence chain for why a lead is qualified.

    This provides the "why" behind every lead recommendation,
    backed by specific facts from the knowledge web.
    """

    __tablename__ = "lead_justifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)

    # Signal category
    signal_category = Column(String(50), nullable=False)  # fit, intent, timing

    # The justification
    signal_type = Column(String(100), nullable=False)  # e.g., "hiring_sales_team"
    signal_description = Column(Text, nullable=False)
    impact_score = Column(Float, default=0.5)  # How much this affects qualification

    # Evidence links (fact IDs that support this justification)
    evidence_fact_ids = Column(JSON, default=list)  # List of EvidencedFact UUIDs
    evidence_summary = Column(Text)  # Human-readable summary of evidence

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    detected_at = Column(DateTime, default=lambda: datetime.now(UTC))  # When signal was detected

    __table_args__ = (
        Index("ix_lead_justifications_lead", "lead_id"),
        Index("ix_lead_justifications_category", "signal_category"),
        Index("ix_lead_justifications_type", "signal_type"),
    )

    def __repr__(self) -> str:
        return f"<LeadJustification {self.signal_category}: {self.signal_type}>"


class CompetitorSignal(Base):
    """Tracked signals about competitor activities.

    Links to evidenced facts for full provenance.
    """

    __tablename__ = "competitor_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    competitor_id = Column(UUID(as_uuid=True), ForeignKey("competitors.id"), nullable=False)

    # Signal details
    signal_type = Column(String(50), nullable=False)  # product, pricing, hiring, funding
    title = Column(String(300), nullable=False)
    description = Column(Text)
    severity = Column(String(20), default="medium")  # low, medium, high, critical

    # Evidence (links to fact IDs)
    primary_fact_id = Column(UUID(as_uuid=True), ForeignKey("evidenced_facts.id"))
    supporting_fact_ids = Column(JSON, default=list)  # Additional fact UUIDs

    # Analysis
    our_response_options = Column(JSON, default=list)
    recommended_action = Column(Text)

    # Status
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime)
    response_status = Column(String(20))  # pending, in_progress, addressed, ignored

    # Timestamps
    detected_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        Index("ix_competitor_signals_competitor", "competitor_id"),
        Index("ix_competitor_signals_type", "signal_type"),
        Index("ix_competitor_signals_severity", "severity"),
        Index("ix_competitor_signals_detected", "detected_at"),
    )

    def __repr__(self) -> str:
        return f"<CompetitorSignal {self.signal_type}: {self.title[:50]}>"


class MCPDataSource(Base):
    """Registry of MCP data sources and their status."""

    __tablename__ = "mcp_data_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Source identification
    name = Column(String(100), nullable=False, unique=True)
    source_type = Column(Enum(SourceType), nullable=False)
    description = Column(Text)

    # Configuration
    endpoint_url = Column(String(500))
    config = Column(JSON, default=dict)  # API keys, settings, etc.

    # Status
    is_enabled = Column(Boolean, default=True)
    is_healthy = Column(Boolean, default=True)
    last_health_check = Column(DateTime)
    last_sync = Column(DateTime)

    # Usage tracking
    total_facts_produced = Column(Integer, default=0)
    facts_today = Column(Integer, default=0)
    avg_confidence = Column(Float, default=0.0)

    # Rate limiting
    rate_limit_per_hour = Column(Integer)
    requests_this_hour = Column(Integer, default=0)
    rate_limit_reset_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_mcp_data_sources_name", "name"),
        Index("ix_mcp_data_sources_type", "source_type"),
        Index("ix_mcp_data_sources_enabled", "is_enabled"),
    )

    def __repr__(self) -> str:
        return f"<MCPDataSource {self.name}>"


# =============================================================================
# Digital Workforce models
# =============================================================================


class WorkforceStatus(str, PyEnum):
    """Status of a digital workforce configuration."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    FAILED = "failed"  # Design run failed — see config.definition["error"]


class ExecutionRunStatus(str, PyEnum):
    """Status of a single workforce execution run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class WorkforceConfig(Base):
    """Digital Workforce configuration for a company.

    Created by WorkforceArchitectAgent from completed analysis.
    Stores the full WorkforceDefinition as JSON plus approval state.
    """

    __tablename__ = "workforce_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analyses.id"), nullable=True)

    status = Column(Enum(WorkforceStatus), default=WorkforceStatus.DRAFT, nullable=False)

    # Full WorkforceDefinition JSON (agent_roster, value_chain, kpis, etc.)
    definition = Column(JSON, nullable=False, default=dict)

    # Subset of agent_types the user has approved for execution
    approved_agents = Column(JSON, default=list)

    # Summary fields for quick display (denormalised from definition)
    executive_summary = Column(Text)
    estimated_weekly_hours_saved = Column(Float, default=0.0)
    estimated_monthly_revenue_impact_sgd = Column(Float, default=0.0)
    agent_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    company = relationship("Company")
    execution_runs = relationship("ExecutionRun", back_populates="workforce_config", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_workforce_configs_company_id", "company_id"),
        Index("ix_workforce_configs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<WorkforceConfig {self.id} ({self.status.value})>"


class ExecutionRun(Base):
    """One execution cycle of the digital workforce.

    Created each time the workforce is triggered (manual or scheduled).
    Tracks step-by-step progress and aggregates metrics.
    """

    __tablename__ = "execution_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workforce_config_id = Column(UUID(as_uuid=True), ForeignKey("workforce_configs.id"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    status = Column(Enum(ExecutionRunStatus), default=ExecutionRunStatus.PENDING, nullable=False)
    trigger = Column(String(50), default="manual")     # "manual", "scheduled", "event"
    trigger_event = Column(String(200))                # e.g. "lead_qualified:uuid"

    # Progress counters
    steps_total = Column(Integer, default=0)
    steps_completed = Column(Integer, default=0)
    steps_failed = Column(Integer, default=0)

    # Execution outcomes
    emails_sent = Column(Integer, default=0)
    crm_records_updated = Column(Integer, default=0)
    leads_contacted = Column(Integer, default=0)

    # Error info
    error_summary = Column(Text)

    # Step-level log (list of dicts: {step, agent, status, result_summary, duration_ms})
    execution_log = Column(JSON, default=list)

    # Timestamps
    started_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    completed_at = Column(DateTime)

    # Relationships
    workforce_config = relationship("WorkforceConfig", back_populates="execution_runs")
    metrics = relationship("ExecutionMetric", back_populates="execution_run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_execution_runs_company_id", "company_id"),
        Index("ix_execution_runs_workforce_config_id", "workforce_config_id"),
        Index("ix_execution_runs_status", "status"),
        Index("ix_execution_runs_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<ExecutionRun {self.id} ({self.status.value})>"


class ExecutionMetric(Base):
    """KPI snapshot captured during or after an execution run.

    Used for time-series monitoring dashboards. One row per metric per run.
    """

    __tablename__ = "execution_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    execution_run_id = Column(UUID(as_uuid=True), ForeignKey("execution_runs.id"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    # Metric identity
    metric_name = Column(String(100), nullable=False)     # "email_open_rate", "deals_created"
    metric_source = Column(String(50), nullable=False)    # "sendgrid", "hubspot", "internal"

    # Values
    value = Column(Float, nullable=False)
    target_value = Column(Float)
    unit = Column(String(30))           # "%", "count", "SGD"
    delta_from_previous = Column(Float) # change vs last run

    # Context
    step_name = Column(String(200))
    agent_type = Column(String(100))
    notes = Column(Text)

    captured_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    execution_run = relationship("ExecutionRun", back_populates="metrics")

    __table_args__ = (
        Index("ix_execution_metrics_run_id", "execution_run_id"),
        Index("ix_execution_metrics_company_id", "company_id"),
        Index("ix_execution_metrics_name_time", "metric_name", "captured_at"),
    )

    def __repr__(self) -> str:
        return f"<ExecutionMetric {self.metric_name}={self.value}>"


# ---------------------------------------------------------------------------
# Signal Intelligence Models
# ---------------------------------------------------------------------------

class SignalType(str, PyEnum):
    """Type of market signal detected."""
    FUNDING = "funding"
    ACQUISITION = "acquisition"
    PRODUCT_LAUNCH = "product_launch"
    REGULATION = "regulation"
    EXPANSION = "expansion"
    HIRING = "hiring"
    LAYOFF = "layoff"
    PARTNERSHIP = "partnership"
    MARKET_TREND = "market_trend"
    COMPETITOR_NEWS = "competitor_news"
    GENERAL_NEWS = "general_news"


class SignalUrgency(str, PyEnum):
    IMMEDIATE = "immediate"      # Act within 24 hours
    THIS_WEEK = "this_week"      # Act within 7 days
    THIS_MONTH = "this_month"    # Monitor and act this month
    MONITOR = "monitor"          # Background signal, low priority


class SignalEvent(Base):
    """A market or competitor signal detected by the Signal Monitor Agent."""
    __tablename__ = "signal_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_type: Mapped[SignalType] = mapped_column(Enum(SignalType), nullable=False, index=True)
    urgency: Mapped[SignalUrgency] = mapped_column(Enum(SignalUrgency), nullable=False, default=SignalUrgency.MONITOR)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "NewsAPI", "Perplexity", "EODHD"
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    competitors_mentioned: Mapped[list] = mapped_column(JSON, default=list)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_actioned: Mapped[bool] = mapped_column(Boolean, default=False)
    actioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    company: Mapped["Company"] = relationship("Company", lazy="select")


# ---------------------------------------------------------------------------
# Outreach Sequence Models
# ---------------------------------------------------------------------------

class SequenceTemplate(Base):
    """A reusable multi-step outreach sequence template."""
    __tablename__ = "sequence_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    # NULL company_id = system/built-in template
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    playbook_type: Mapped[str] = mapped_column(String(50), nullable=False)  # PlaybookType enum value
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    total_duration_days: Mapped[int] = mapped_column(Integer, default=14)
    is_system_template: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    steps: Mapped[list["SequenceStep"]] = relationship("SequenceStep", back_populates="template", order_by="SequenceStep.step_number", cascade="all, delete-orphan")
    enrollments: Mapped[list["SequenceEnrollment"]] = relationship("SequenceEnrollment", back_populates="template")


class SequenceStep(Base):
    """A single step within a sequence template."""
    __tablename__ = "sequence_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sequence_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    day_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Days from enrollment date
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "cold_intro", "followup", "breakup" etc.
    subject_pattern: Mapped[str] = mapped_column(String(300), nullable=False)  # Template with {first_name} etc.
    body_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)  # Prompt context for personalisation
    channel: Mapped[str] = mapped_column(String(20), default="email")
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)  # Always True

    # Relationships
    template: Mapped["SequenceTemplate"] = relationship("SequenceTemplate", back_populates="steps")


class EnrollmentStatus(str, PyEnum):
    ACTIVE = "active"
    PAUSED = "paused"       # Replied or manually paused
    COMPLETED = "completed"  # All steps sent
    REJECTED = "rejected"    # Approval rejected
    OPTED_OUT = "opted_out"  # Unsubscribed


class SequenceEnrollment(Base):
    """A lead enrolled in a specific sequence template."""
    __tablename__ = "sequence_enrollments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sequence_templates.id"), nullable=False)
    status: Mapped[EnrollmentStatus] = mapped_column(Enum(EnrollmentStatus), default=EnrollmentStatus.ACTIVE, nullable=False, index=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0)  # 0-indexed
    next_step_due: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pause_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    emails_sent: Mapped[int] = mapped_column(Integer, default=0)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trigger_signal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("signal_events.id"), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    # Relationships
    lead: Mapped["Lead"] = relationship("Lead", lazy="select")
    template: Mapped["SequenceTemplate"] = relationship("SequenceTemplate", back_populates="enrollments")


# ---------------------------------------------------------------------------
# Approval Queue
# ---------------------------------------------------------------------------

class ApprovalStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED_APPROVED = "edited_approved"  # User edited the content then approved


class ApprovalQueueItem(Base):
    """A pending outreach action awaiting human approval."""
    __tablename__ = "approval_queue"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    enrollment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sequence_enrollments.id", ondelete="CASCADE"), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False, index=True)
    # Proposed email content
    proposed_subject: Mapped[str] = mapped_column(String(500), nullable=False)
    proposed_body: Mapped[str] = mapped_column(Text, nullable=False)
    final_subject: Mapped[str | None] = mapped_column(String(500), nullable=True)   # After edit
    final_body: Mapped[str | None] = mapped_column(Text, nullable=True)              # After edit
    to_email: Mapped[str] = mapped_column(String(300), nullable=False)
    to_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sequence_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)     # User email
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # Auto-expire stale items
    scheduled_send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)     # SendGrid message ID


# ---------------------------------------------------------------------------
# Attribution & ROI Tracking
# ---------------------------------------------------------------------------

class AttributionEvent(Base):
    """Tracks the journey from outreach action to business outcome."""
    __tablename__ = "attribution_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True)
    approval_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("approval_queue.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # event_type values: "email_sent", "email_opened", "email_clicked", "reply_received",
    #                    "meeting_booked", "meeting_held", "proposal_sent", "deal_closed"
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    pipeline_value_sgd: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    recorded_by: Mapped[str] = mapped_column(String(50), default="system")  # "system" or user email


# ---------------------------------------------------------------------------
# Playbook Templates (built-in + custom)
# ---------------------------------------------------------------------------

class PlaybookTemplate(Base):
    """Pre-built GTM playbook configurations."""
    __tablename__ = "playbook_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    playbook_type: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    best_for: Mapped[str] = mapped_column(Text, nullable=False)
    steps_count: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    success_rate_benchmark: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sequence_config: Mapped[dict] = mapped_column(JSON, default=dict)  # Full step config
    scoring_weights: Mapped[dict] = mapped_column(JSON, default=dict)  # PlaybookFitScorer weights
    is_singapore_specific: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# Market Intelligence Database — Phase 3
# ---------------------------------------------------------------------------


class CompanyListingType(str, PyEnum):
    """Type of listed instrument."""
    COMMON_STOCK = "common_stock"
    REIT = "reit"
    ETF = "etf"
    BUSINESS_TRUST = "business_trust"
    PREFERRED = "preferred"


class FinancialPeriodType(str, PyEnum):
    """Annual or quarterly financial period."""
    ANNUAL = "annual"
    QUARTERLY = "quarterly"


class MarketVertical(Base):
    """Singapore industry vertical taxonomy — SSIC-anchored.

    12 primary verticals mapped to SSIC 2020 section codes.
    Used as the spine for all benchmarking and signal classification.
    """
    __tablename__ = "market_verticals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    ssic_sections: Mapped[list] = mapped_column(JSON, default=list)    # e.g. ["K", "J"]
    ssic_codes: Mapped[list] = mapped_column(JSON, default=list)       # specific 5-digit codes
    gics_sectors: Mapped[list] = mapped_column(JSON, default=list)     # EODHD GicsSector values
    keywords: Mapped[list] = mapped_column(JSON, default=list)         # for news classification
    is_reit_vertical: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    listed_companies: Mapped[list["ListedCompany"]] = relationship(
        "ListedCompany", back_populates="vertical", lazy="select"
    )
    benchmarks: Mapped[list["VerticalBenchmark"]] = relationship(
        "VerticalBenchmark", back_populates="vertical", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<MarketVertical {self.slug}>"


class ListedCompany(Base):
    """SGX-listed or overseas-listed Singapore company.

    Populated from EODHD exchange-symbol-list/SG and a curated list
    of SG-founded companies on US/HK exchanges.

    Does NOT store individual contacts (no PDPA concern — B2B company data).
    """
    __tablename__ = "listed_companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False)  # SG, US, HK, etc.
    isin: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    listing_type: Mapped[CompanyListingType] = mapped_column(
        Enum(CompanyListingType), default=CompanyListingType.COMMON_STOCK, nullable=False
    )
    currency: Mapped[str] = mapped_column(String(5), default="SGD")
    vertical_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("market_verticals.id"), nullable=True, index=True
    )

    # EODHD General fields
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    gics_sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gics_industry: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Snapshot financials (from Highlights — refreshed with each sync)
    market_cap_sgd: Mapped[float | None] = mapped_column(Float, nullable=True)
    pe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    ev_ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_ttm_sgd: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    roe: Mapped[float | None] = mapped_column(Float, nullable=True)
    dividend_yield: Mapped[float | None] = mapped_column(Float, nullable=True)

    # REIT-specific (null for non-REITs)
    nav_per_unit: Mapped[float | None] = mapped_column(Float, nullable=True)
    dpu_ttm: Mapped[float | None] = mapped_column(Float, nullable=True)       # Distribution per unit
    gearing_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)  # % debt/assets

    # ESG Scores (from EODHD ESGScores section — point-in-time, refreshed with each sync)
    esg_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    esg_environment: Mapped[float | None] = mapped_column(Float, nullable=True)
    esg_social: Mapped[float | None] = mapped_column(Float, nullable=True)
    esg_governance: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Analyst Consensus (from EODHD AnalystRatings section)
    analyst_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    analyst_target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    analyst_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Metadata
    is_sg_incorporated: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    vertical: Mapped["MarketVertical | None"] = relationship("MarketVertical", back_populates="listed_companies")
    financial_snapshots: Mapped[list["CompanyFinancialSnapshot"]] = relationship(
        "CompanyFinancialSnapshot", back_populates="company", lazy="select"
    )

    __table_args__ = (
        Index("ix_listed_companies_ticker_exchange", "ticker", "exchange", unique=True),
        Index("ix_listed_companies_vertical", "vertical_id"),
        Index("ix_listed_companies_market_cap", "market_cap_sgd"),
    )

    def __repr__(self) -> str:
        return f"<ListedCompany {self.ticker}.{self.exchange} ({self.name})>"


class CompanyFinancialSnapshot(Base):
    """Income statement, balance sheet, and cash flow for a listed company.

    One row per company per period (annual or quarterly).
    All monetary values normalised to SGD using exchange rate at period end.

    Source: EODHD fundamentals API → Financials.Income_Statement,
    Balance_Sheet, Cash_Flow sections.
    """
    __tablename__ = "company_financial_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listed_companies.id"), nullable=False, index=True
    )
    period_type: Mapped[FinancialPeriodType] = mapped_column(
        Enum(FinancialPeriodType), nullable=False
    )
    period_end_date: Mapped[str] = mapped_column(String(10), nullable=False)   # YYYY-MM-DD
    filing_currency: Mapped[str] = mapped_column(String(5), default="SGD")
    fx_to_sgd: Mapped[float] = mapped_column(Float, default=1.0)               # multiplier to SGD

    # Income Statement (in SGD)
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)
    ebit: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    eps: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Operational detail (in SGD) — GTM intelligence
    cost_of_revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    selling_general_administrative: Mapped[float | None] = mapped_column(Float, nullable=True)
    research_development: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    interest_expense: Mapped[float | None] = mapped_column(Float, nullable=True)
    depreciation_amortization: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Computed margins (0–1 float, null if revenue = 0)
    gross_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    ebitda_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_margin: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Derived ratios from operational detail (null if revenue = 0 or field absent)
    sga_to_revenue: Mapped[float | None] = mapped_column(Float, nullable=True)    # SG&A / revenue
    rnd_to_revenue: Mapped[float | None] = mapped_column(Float, nullable=True)    # R&D / revenue
    operating_margin: Mapped[float | None] = mapped_column(Float, nullable=True)  # operating_income / revenue

    # YoY growth rates (null for oldest period)
    revenue_growth_yoy: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_income_growth_yoy: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Balance Sheet (in SGD)
    total_assets: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_debt: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash_and_equivalents: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_debt: Mapped[float | None] = mapped_column(Float, nullable=True)       # total_debt - cash

    # Derived ratios
    roe: Mapped[float | None] = mapped_column(Float, nullable=True)            # net_income / equity
    net_debt_ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Cash Flow (in SGD)
    operating_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)
    capex: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Metadata
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    company: Mapped["ListedCompany"] = relationship("ListedCompany", back_populates="financial_snapshots")

    __table_args__ = (
        Index(
            "ix_financial_snapshots_company_period",
            "company_id", "period_type", "period_end_date",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<CompanyFinancialSnapshot {self.company_id} {self.period_type} {self.period_end_date}>"


class VerticalBenchmark(Base):
    """Precomputed percentile benchmarks for a vertical + period.

    Updated by the weekly financial sync job.
    Gives: P25/P50/P75/P90 for each key metric within the vertical.

    Example: for Fintech, annual 2024:
      revenue_growth_yoy: P25=0.05, P50=0.15, P75=0.35, P90=0.60
      gross_margin:       P25=0.40, P50=0.55, P75=0.65, P90=0.75
    """
    __tablename__ = "vertical_benchmarks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vertical_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("market_verticals.id"), nullable=False, index=True
    )
    period_type: Mapped[FinancialPeriodType] = mapped_column(Enum(FinancialPeriodType), nullable=False)
    period_label: Mapped[str] = mapped_column(String(20), nullable=False)      # e.g. "2024", "2024-Q3"
    company_count: Mapped[int] = mapped_column(Integer, nullable=False)        # N companies in sample

    # Percentile distributions stored as JSON: {"p25": x, "p50": x, "p75": x, "p90": x}
    revenue_growth_yoy: Mapped[dict] = mapped_column(JSON, default=dict)
    gross_margin: Mapped[dict] = mapped_column(JSON, default=dict)
    ebitda_margin: Mapped[dict] = mapped_column(JSON, default=dict)
    net_margin: Mapped[dict] = mapped_column(JSON, default=dict)
    roe: Mapped[dict] = mapped_column(JSON, default=dict)
    net_debt_ebitda: Mapped[dict] = mapped_column(JSON, default=dict)
    revenue_ttm_sgd: Mapped[dict] = mapped_column(JSON, default=dict)         # Revenue scale distribution

    # Leader / laggard snapshots (top 3 and bottom 3 by revenue growth)
    leaders: Mapped[list] = mapped_column(JSON, default=list)                 # [{"ticker", "name", "metric", "value"}]
    laggards: Mapped[list] = mapped_column(JSON, default=list)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    vertical: Mapped["MarketVertical"] = relationship("MarketVertical", back_populates="benchmarks")

    __table_args__ = (
        Index(
            "ix_vertical_benchmarks_vertical_period",
            "vertical_id", "period_type", "period_label",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<VerticalBenchmark {self.vertical_id} {self.period_label}>"


class MarketArticle(Base):
    """RSS/news article ingested from Singapore business publications.

    Sources: Business Times, e27, Tech in Asia, Vulcan Post, Deal Street Asia,
    MAS press releases, EnterpriseSG announcements, SGX RegNet.

    Embeddings stored as JSON text (serialised list of 1536 floats from
    OpenAI text-embedding-3-small). This works in both SQLite (dev) and
    PostgreSQL (prod). On PostgreSQL, a pgvector index can be added via
    raw SQL migration for ANN search.
    """
    __tablename__ = "market_articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)           # First 500 chars of content
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Classification (LLM-assigned)
    vertical_slug: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    signal_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # funding, acquisition, etc.
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)    # positive, neutral, negative
    mentioned_tickers: Mapped[list] = mapped_column(JSON, default=list)         # [{"ticker", "exchange"}]

    # Vector embedding — JSON array of 1536 floats (text-embedding-3-small)
    # Null if embedding not yet computed or OpenAI unavailable
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_classified: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_market_articles_published_vertical", "published_at", "vertical_slug"),
        Index("ix_market_articles_source_published", "source_name", "published_at"),
    )

    def __repr__(self) -> str:
        return f"<MarketArticle {self.source_name}: {self.title[:60]}>"


class DocumentType(str, PyEnum):
    """Type of corporate document."""
    ANNUAL_REPORT = "annual_report"
    SUSTAINABILITY_REPORT = "sustainability_report"
    EARNINGS_RELEASE = "earnings_release"
    MATERIAL_ANNOUNCEMENT = "material_announcement"
    PRESS_RELEASE = "press_release"
    INVESTOR_PRESENTATION = "investor_presentation"
    CIRCULAR = "circular"


class CompanyDocument(Base):
    """Corporate document (PDF or HTML) filed by a listed company.

    Populated from SGX RegNet announcements API and company IR pages.
    Tracks download status and processing state (chunked for RAG).

    Storage: local filesystem at DOCUMENT_STORE_PATH/{company_id}/{type}/{filename}
    For production: swap file_path for an S3 object key.
    """
    __tablename__ = "company_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listed_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listed_companies.id"), nullable=False, index=True
    )
    document_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False, unique=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)   # local path after download
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    fiscal_year: Mapped[str | None] = mapped_column(String(4), nullable=True)      # e.g. "2024"

    # Processing state
    is_downloaded: Mapped[bool] = mapped_column(Boolean, default=False)
    is_chunked: Mapped[bool] = mapped_column(Boolean, default=False)           # RAG chunks created
    download_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # SGX RegNet reference (if sourced from SGX)
    sgx_announcement_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    sgx_category: Mapped[str | None] = mapped_column(String(200), nullable=True)

    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    listed_company: Mapped["ListedCompany"] = relationship("ListedCompany")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan", lazy="select"
    )

    __table_args__ = (
        Index("ix_company_documents_company_type", "listed_company_id", "document_type"),
        Index("ix_company_documents_fiscal_year", "listed_company_id", "fiscal_year"),
    )

    def __repr__(self) -> str:
        return f"<CompanyDocument {self.document_type.value}: {self.title[:60]}>"


class DocumentChunk(Base):
    """A text chunk extracted from a CompanyDocument, with embedding.

    Chunks are created by the document processing pipeline:
      1. PDF → full text (pypdf)
      2. Section detection (heuristic headers)
      3. Chunk into ~400 token segments with 50-token overlap
      4. Embed with OpenAI text-embedding-3-small → JSON in `embedding`

    Used for RAG: agents query chunks semantically to answer questions
    like "what is DBS's digital strategy?" or "what ESG targets did Keppel set?"
    """
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company_documents.id"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)            # 0-based order within doc
    section_name: Mapped[str | None] = mapped_column(String(200), nullable=True) # detected section header
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)

    # Embedding: JSON-serialised list of 1536 floats (text-embedding-3-small)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    document: Mapped["CompanyDocument"] = relationship("CompanyDocument", back_populates="chunks")

    __table_args__ = (
        Index("ix_document_chunks_document_index", "document_id", "chunk_index", unique=True),
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk doc={self.document_id} [{self.chunk_index}] {self.section_name}>"


class CompanyExecutive(Base):
    """Executive / board member at a listed company.

    Populated from EODHD General.Officers JSON field.
    Supplemented by SGX board-change announcements.

    Used for executive news monitoring: the news pipeline queries each
    executive's name in NewsAPI/RSS to surface their public statements,
    interviews, and market-relevant announcements.

    NOTE: No LinkedIn / social scraping. Sources are:
      - EODHD company data (name, title, since-date, age)
      - SGX change-in-director filings (real-time appointment/resignation)
      - NewsAPI mentions by full name + company
    """
    __tablename__ = "company_executives"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listed_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listed_companies.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    is_ceo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_cfo: Mapped[bool] = mapped_column(Boolean, default=False)
    is_chair: Mapped[bool] = mapped_column(Boolean, default=False)
    since_date: Mapped[str | None] = mapped_column(String(10), nullable=True)   # YYYY-MM-DD
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)                # EODHD bio if available

    # News monitoring state
    last_news_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    listed_company: Mapped["ListedCompany"] = relationship("ListedCompany")

    __table_args__ = (
        Index("ix_company_executives_company_name", "listed_company_id", "name", unique=True),
        Index("ix_company_executives_company_ceo", "listed_company_id", "is_ceo"),
    )


# ---------------------------------------------------------------------------
# Knowledge Layer — Research Cache
# ---------------------------------------------------------------------------


class ResearchCache(Base):
    """Staging table for real-time research results before embedding into Qdrant.

    Agents (Market Intelligence, Competitor Analyst, etc.) write raw Perplexity/
    NewsAPI research here during _act(). A background job embeds and upserts
    public rows to the research_cache_sg Qdrant collection.

    Privacy: rows with company_id set are private to that company and NEVER
    upserted to the shared Qdrant index (is_public stays False).
    """

    __tablename__ = "research_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # "perplexity" | "newsapi"
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    vertical_slug: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_embedded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON float array
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_research_cache_public_unembedded", "is_public", "is_embedded"),
        Index("ix_research_cache_vertical", "vertical_slug"),
    )


class SgKnowledgeArticle(Base):
    """Singapore government reference data: grants, regulations, enforcement decisions.

    Populated by the SgReferenceScraper scheduler job (weekly Sunday 04:00 SGT).
    Used by KnowledgeMCPServer.get_sg_reference() to ground agents in live
    Singapore market context.

    Privacy: Contains only publicly available government data — no personal data.
    """
    __tablename__ = "sg_knowledge_articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    category_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    effective_date: Mapped[str | None] = mapped_column(String(20), nullable=True)   # ISO date string
    last_verified: Mapped[str | None] = mapped_column(String(20), nullable=True)    # ISO date string
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_embedded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON float array

    __table_args__ = (
        Index("ix_sg_knowledge_source_type", "source", "category_type"),
        Index("ix_sg_knowledge_unembedded", "is_embedded"),
    )
