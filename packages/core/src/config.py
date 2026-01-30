"""GTM Advisor Configuration Management."""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Deployment environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


# NOTE: SubscriptionTier is defined in packages/database/src/models.py
# Use: from packages.database.src.models import SubscriptionTier
# Values: FREE, TIER1, TIER2


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

    # Rate Limiting Configuration (maps to database SubscriptionTier enum: FREE, TIER1, TIER2)
    # All values must be >= 1
    rate_limit_free_requests: int = Field(
        default=10, ge=1, description="Free tier daily API requests"
    )
    rate_limit_tier1_requests: int = Field(
        default=100, ge=1, description="Tier1 daily API requests"
    )
    rate_limit_tier2_requests: int = Field(
        default=500, ge=1, description="Tier2 daily API requests"
    )

    rate_limit_free_analyses: int = Field(default=3, ge=1, description="Free tier daily analyses")
    rate_limit_tier1_analyses: int = Field(default=20, ge=1, description="Tier1 daily analyses")
    rate_limit_tier2_analyses: int = Field(default=100, ge=1, description="Tier2 daily analyses")

    # Cache Configuration
    user_cache_ttl_seconds: int = Field(
        default=300, ge=10, le=3600, description="User cache TTL (10-3600 seconds)"
    )
    user_cache_max_size: int = Field(default=10000, ge=100, description="Maximum cached users")

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Ensure JWT secret is strong enough in production."""
        # Access environment from context if available
        env = os.getenv("GTM_ENVIRONMENT", "development")
        if env == "production":
            if len(v) < 32:
                raise ValueError("JWT secret must be at least 32 characters in production")
            if v == "dev-secret-change-in-production-32chars":
                raise ValueError("Cannot use default JWT secret in production")
        return v

    def validate_production_requirements(self) -> list[str]:
        """Validate all production requirements are met.

        Returns:
            List of validation errors (empty if all valid)
        """
        errors = []

        if not self.is_production:
            return errors  # Only validate in production

        # Required infrastructure
        if not self.postgres_url:
            errors.append("GTM_POSTGRES_URL is required in production")

        if not self.redis_url:
            errors.append("GTM_REDIS_URL is required in production")

        # Security requirements
        if len(self.jwt_secret) < 32:
            errors.append("JWT secret must be at least 32 characters")

        if self.jwt_secret == "dev-secret-change-in-production-32chars":
            errors.append("Cannot use default JWT secret in production")

        # Database SSL
        if self.postgres_url and "sslmode=require" not in self.postgres_url:
            errors.append("PostgreSQL connection should use SSL (sslmode=require)")

        # Redis TLS
        if self.redis_url and not self.redis_url.startswith("rediss://"):
            errors.append("Redis connection should use TLS (rediss:// protocol)")

        # CORS origins should not include localhost in production
        localhost_origins = [o for o in self.cors_origins if "localhost" in o or "127.0.0.1" in o]
        if localhost_origins:
            errors.append(
                f"CORS origins should not include localhost in production: {localhost_origins}"
            )

        # Required API keys
        if not self.openai_api_key and not self.anthropic_api_key:
            errors.append("At least one LLM API key (OpenAI or Anthropic) is required")

        return errors

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == Environment.DEVELOPMENT

    def get_rate_limit_requests(self, tier_name: str) -> int:
        """Get daily request limit for a tier.

        Args:
            tier_name: Tier name (free, tier1, tier2) - case insensitive

        Returns:
            Daily request limit
        """
        tier_name = tier_name.lower()
        limits = {
            "free": self.rate_limit_free_requests,
            "tier1": self.rate_limit_tier1_requests,
            "tier2": self.rate_limit_tier2_requests,
        }
        return limits.get(tier_name, self.rate_limit_free_requests)

    def get_rate_limit_analyses(self, tier_name: str) -> int:
        """Get daily analysis limit for a tier.

        Args:
            tier_name: Tier name (free, tier1, tier2) - case insensitive

        Returns:
            Daily analysis limit
        """
        tier_name = tier_name.lower()
        limits = {
            "free": self.rate_limit_free_analyses,
            "tier1": self.rate_limit_tier1_analyses,
            "tier2": self.rate_limit_tier2_analyses,
        }
        return limits.get(tier_name, self.rate_limit_free_analyses)


@lru_cache
def get_config() -> GTMConfig:
    """Get cached configuration instance."""
    return GTMConfig()


def clear_config_cache() -> None:
    """Clear the config cache. Use when config needs to be reloaded."""
    get_config.cache_clear()
