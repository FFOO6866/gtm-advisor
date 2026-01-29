"""SQLAlchemy models for GTM Advisor.

Tables:
- users: User accounts with subscription tiers
- companies: Company profiles for analysis
- analyses: GTM analysis results
- consents: PDPA consent records
- audit_logs: Audit trail for compliance
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

    # GTM context
    goals = Column(JSON, default=list)  # List of goals
    challenges = Column(JSON, default=list)  # List of challenges
    competitors = Column(JSON, default=list)  # List of competitor names
    target_markets = Column(JSON, default=list)  # List of markets
    value_proposition = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="companies")
    analyses = relationship("Analysis", back_populates="company")

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
