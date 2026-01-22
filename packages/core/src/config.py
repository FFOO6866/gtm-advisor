"""GTM Advisor Configuration Management."""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Deployment environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class SubscriptionTier(str, Enum):
    """Subscription tiers for GTM Advisor."""

    FREE = "free"  # Trial/demo
    STARTER = "starter"  # S$500/month
    GROWTH = "growth"  # S$1000/month
    SCALE = "scale"  # S$2000/month
    ENTERPRISE = "enterprise"  # Custom


class GTMConfig(BaseSettings):
    """Central configuration for GTM Advisor platform."""

    model_config = SettingsConfigDict(
        env_prefix="GTM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Environment
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Deployment environment",
    )

    # LLM Configuration
    default_llm_provider: str = Field(
        default="openai",
        description="Default LLM provider (openai, anthropic, perplexity)",
    )
    default_model: str = Field(
        default="gpt-4o",
        description="Default LLM model",
    )

    # API Keys (loaded from environment)
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    perplexity_api_key: str | None = Field(default=None, alias="PERPLEXITY_API_KEY")
    newsapi_api_key: str | None = Field(default=None, alias="NEWSAPI_API_KEY")
    eodhd_api_key: str | None = Field(default=None, alias="EODHD_API_KEY")

    # Infrastructure
    postgres_url: str | None = Field(
        default=None,
        description="PostgreSQL connection URL",
    )
    redis_url: str | None = Field(
        default=None,
        description="Redis connection URL",
    )
    qdrant_url: str | None = Field(
        default=None,
        description="Qdrant vector DB URL",
    )

    # Security
    jwt_secret: str = Field(
        default="dev-secret-change-in-production-32chars",
        description="JWT signing secret (32+ chars in production)",
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins",
    )

    # Feature Flags
    enable_governance: bool = Field(
        default=True,
        description="Enable governance policies",
    )
    enable_observability: bool = Field(
        default=False,
        description="Enable tracing and metrics",
    )
    enable_pdpa_compliance: bool = Field(
        default=True,
        description="Enable PDPA compliance checks",
    )

    # Observability
    jaeger_url: str | None = Field(default=None)
    prometheus_port: int = Field(default=9090)

    # Business Configuration
    tier_starter_price: int = Field(default=500, description="Starter tier price (SGD)")
    tier_growth_price: int = Field(default=1000, description="Growth tier price (SGD)")
    tier_scale_price: int = Field(default=2000, description="Scale tier price (SGD)")

    tier_starter_limit: int = Field(default=50, description="Starter tier daily limit")
    tier_growth_limit: int = Field(default=200, description="Growth tier daily limit")
    tier_scale_limit: int = Field(default=1000, description="Scale tier daily limit")

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: str, info: Any) -> str:
        """Ensure JWT secret is strong enough in production."""
        # Access environment from context if available
        env = os.getenv("GTM_ENVIRONMENT", "development")
        if env == "production" and len(v) < 32:
            raise ValueError("JWT secret must be at least 32 characters in production")
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == Environment.DEVELOPMENT

    def get_tier_limit(self, tier: SubscriptionTier) -> int:
        """Get daily request limit for a subscription tier."""
        limits = {
            SubscriptionTier.FREE: 10,
            SubscriptionTier.STARTER: self.tier_starter_limit,
            SubscriptionTier.GROWTH: self.tier_growth_limit,
            SubscriptionTier.SCALE: self.tier_scale_limit,
            SubscriptionTier.ENTERPRISE: 100000,  # Effectively unlimited
        }
        return limits.get(tier, 10)

    def get_tier_price(self, tier: SubscriptionTier) -> int:
        """Get monthly price for a subscription tier (SGD)."""
        prices = {
            SubscriptionTier.FREE: 0,
            SubscriptionTier.STARTER: self.tier_starter_price,
            SubscriptionTier.GROWTH: self.tier_growth_price,
            SubscriptionTier.SCALE: self.tier_scale_price,
            SubscriptionTier.ENTERPRISE: -1,  # Custom pricing
        }
        return prices.get(tier, 0)


@lru_cache
def get_config() -> GTMConfig:
    """Get cached configuration instance."""
    return GTMConfig()
