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
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    Float,
    DateTime,
    Enum,
    ForeignKey,
    JSON,
    Index,
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
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

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
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
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
