"""Database package for GTM Advisor."""

from .models import (
    Base,
    User,
    Company,
    Analysis,
    Consent,
    AuditLog,
    Competitor,
    CompetitorAlert,
    ICP,
    Persona,
    Lead,
    Campaign,
    MarketInsight,
    # Enums
    SubscriptionTier,
    AnalysisStatus,
    ConsentPurpose,
    ThreatLevel,
    LeadStatus,
    CampaignStatus,
)
from .session import get_db, get_db_session, init_db, close_db, AsyncSessionLocal

__all__ = [
    # Models
    "Base",
    "User",
    "Company",
    "Analysis",
    "Consent",
    "AuditLog",
    "Competitor",
    "CompetitorAlert",
    "ICP",
    "Persona",
    "Lead",
    "Campaign",
    "MarketInsight",
    # Enums
    "SubscriptionTier",
    "AnalysisStatus",
    "ConsentPurpose",
    "ThreatLevel",
    "LeadStatus",
    "CampaignStatus",
    # Session
    "get_db",
    "get_db_session",
    "init_db",
    "close_db",
    "AsyncSessionLocal",
]
