"""Authentication models for GTM Advisor Gateway."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field


class SubscriptionTier(str, Enum):
    """User subscription tiers matching business plan."""

    FREE = "free"  # Trial/limited access
    TIER1 = "tier1"  # $700/month - Self-serve AI marketing
    TIER2 = "tier2"  # $7,000/month - Advisory + Governance


class UserBase(BaseModel):
    """Base user model with shared fields."""

    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=100)
    company_name: Optional[str] = Field(None, max_length=200)


class UserCreate(UserBase):
    """Model for user registration."""

    password: str = Field(..., min_length=8, max_length=100)


class User(UserBase):
    """Public user model (without password)."""

    id: UUID = Field(default_factory=uuid4)
    tier: SubscriptionTier = SubscriptionTier.FREE
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Usage tracking
    daily_requests: int = 0
    last_request_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserInDB(User):
    """User model with hashed password (for database storage)."""

    hashed_password: str


class Token(BaseModel):
    """JWT token response model."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenData(BaseModel):
    """Data extracted from JWT token."""

    user_id: UUID
    email: str
    tier: SubscriptionTier
    exp: datetime


class LoginRequest(BaseModel):
    """Login request model."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Token refresh request model."""

    refresh_token: str
