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
"""

from datetime import datetime
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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

    # Enrichment metadata
    enrichment_confidence = Column(Float, default=0.0)
    last_enriched_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    last_updated = Column(DateTime, default=datetime.utcnow)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

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
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    last_updated = Column(DateTime, default=datetime.utcnow)
    fact_count = Column(Integer, default=0)  # Number of facts about this entity

    # Status
    is_active = Column(Boolean, default=True)
    merged_into_id = Column(UUID(as_uuid=True))  # If entity was merged/deduplicated

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow)  # When signal was detected

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
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_mcp_data_sources_name", "name"),
        Index("ix_mcp_data_sources_type", "source_type"),
        Index("ix_mcp_data_sources_enabled", "is_enabled"),
    )

    def __repr__(self) -> str:
        return f"<MCPDataSource {self.name}>"
