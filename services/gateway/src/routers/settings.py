"""User settings API endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import SubscriptionTier
from packages.database.src.models import User as DBUser
from packages.database.src.session import get_db_session

from ..auth.dependencies import get_current_active_user
from ..auth.models import User
from ..schemas.settings import (
    AgentPreferences,
    APIKeySettings,
    DisplayPreferences,
    NotificationPreferences,
    SubscriptionInfo,
    SubscriptionTiersResponse,
    UserPreferences,
    UserSettingsResponse,
    UserSettingsUpdate,
)

logger = structlog.get_logger()
router = APIRouter()

# Subscription tier details
TIER_DETAILS = {
    SubscriptionTier.FREE: {
        "display_name": "Free",
        "price_monthly": 0,
        "currency": "SGD",
        "features": [
            "5 analyses per month",
            "Basic market research",
            "3 competitors tracked",
            "Email support",
        ],
        "limits": {
            "daily_requests": 10,
            "analyses_per_month": 5,
            "competitors": 3,
            "leads_per_run": 5,
            "campaigns": 2,
        },
    },
    SubscriptionTier.TIER1: {
        "display_name": "Professional",
        "price_monthly": 700,
        "currency": "SGD",
        "features": [
            "50 analyses per month",
            "Advanced market intelligence",
            "10 competitors tracked",
            "Priority support",
            "Battle cards",
            "Campaign generation",
        ],
        "limits": {
            "daily_requests": 100,
            "analyses_per_month": 50,
            "competitors": 10,
            "leads_per_run": 20,
            "campaigns": 10,
        },
    },
    SubscriptionTier.TIER2: {
        "display_name": "Enterprise",
        "price_monthly": 7000,
        "currency": "SGD",
        "features": [
            "Unlimited analyses",
            "Full market intelligence suite",
            "Unlimited competitors",
            "Dedicated support",
            "Custom integrations",
            "White-label exports",
            "Team collaboration",
        ],
        "limits": {
            "daily_requests": 1000,
            "analyses_per_month": -1,  # Unlimited
            "competitors": -1,  # Unlimited
            "leads_per_run": 50,
            "campaigns": -1,  # Unlimited
        },
    },
}


def get_tier_limits(tier: SubscriptionTier) -> dict:
    """Get limits for a subscription tier."""
    return TIER_DETAILS.get(tier, TIER_DETAILS[SubscriptionTier.FREE])["limits"]


def db_user_to_settings_response(user: DBUser) -> UserSettingsResponse:
    """Convert database user model to settings response."""
    tier = user.tier or SubscriptionTier.FREE
    tier_details = TIER_DETAILS.get(tier, TIER_DETAILS[SubscriptionTier.FREE])
    tier_limits = tier_details["limits"]
    daily_limit = tier_limits["daily_requests"]

    # Parse preferences or use defaults
    prefs = user.preferences or {}
    notifications = NotificationPreferences(**prefs.get("notifications", {}))
    display = DisplayPreferences(**prefs.get("display", {}))
    agents = AgentPreferences(**prefs.get("agents", {}))

    # API key status (never return actual keys)
    api_keys_configured = APIKeySettings(
        openai_configured=prefs.get("api_keys", {}).get("openai_configured", False),
        perplexity_configured=prefs.get("api_keys", {}).get("perplexity_configured", False),
        newsapi_configured=prefs.get("api_keys", {}).get("newsapi_configured", False),
        eodhd_configured=prefs.get("api_keys", {}).get("eodhd_configured", False),
    )

    return UserSettingsResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        company_name=user.company_name,
        tier=tier.value,
        tier_display_name=tier_details["display_name"],
        tier_limits=tier_limits,
        daily_requests=user.daily_requests or 0,
        daily_limit=daily_limit,
        usage_percentage=(user.daily_requests or 0) / daily_limit * 100 if daily_limit > 0 else 0,
        preferences=UserPreferences(
            notifications=notifications,
            display=display,
            agents=agents,
        ),
        api_keys_configured=api_keys_configured,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("/me", response_model=UserSettingsResponse)
async def get_current_user_settings(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> UserSettingsResponse:
    """Get current user's settings."""
    # Fetch fresh user data from database
    user = await db.get(DBUser, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return db_user_to_settings_response(user)


@router.patch("/me", response_model=UserSettingsResponse)
async def update_current_user_settings(
    data: UserSettingsUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> UserSettingsResponse:
    """Update current user's settings."""
    user = await db.get(DBUser, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update basic fields
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.company_name is not None:
        user.company_name = data.company_name

    # Update preferences
    if data.preferences is not None:
        current_prefs = user.preferences or {}
        pref_data = data.preferences.model_dump(exclude_none=True)

        # Merge preferences
        for key, value in pref_data.items():
            if value is not None:
                current_prefs[key] = value

        user.preferences = current_prefs

    # Handle API keys (store only the configured status, not the actual keys)
    if data.api_keys is not None:
        current_prefs = user.preferences or {}
        api_keys_status = current_prefs.get("api_keys", {})

        # Only update the configured status (actual keys would be stored securely elsewhere)
        if data.api_keys.openai_api_key:
            api_keys_status["openai_configured"] = True
        if data.api_keys.perplexity_api_key:
            api_keys_status["perplexity_configured"] = True
        if data.api_keys.newsapi_api_key:
            api_keys_status["newsapi_configured"] = True
        if data.api_keys.eodhd_api_key:
            api_keys_status["eodhd_configured"] = True

        current_prefs["api_keys"] = api_keys_status
        user.preferences = current_prefs

    await db.flush()

    logger.info("user_settings_updated", user_id=str(current_user.id)[:8])
    return db_user_to_settings_response(user)


@router.get("/tiers", response_model=SubscriptionTiersResponse)
async def get_subscription_tiers(
    current_user: User = Depends(get_current_active_user),
) -> SubscriptionTiersResponse:
    """Get all available subscription tiers."""
    current_tier = current_user.tier or SubscriptionTier.FREE

    tiers = []
    for tier, details in TIER_DETAILS.items():
        tiers.append(
            SubscriptionInfo(
                tier=tier.value,
                display_name=details["display_name"],
                price_monthly=details["price_monthly"],
                currency=details["currency"],
                features=details["features"],
                limits=details["limits"],
                is_current=tier == current_tier,
            )
        )

    return SubscriptionTiersResponse(
        tiers=tiers,
        current_tier=current_tier.value,
    )


@router.get("/usage")
async def get_usage_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get current usage statistics for the user."""
    user = await db.get(DBUser, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    tier = user.tier or SubscriptionTier.FREE
    limits = get_tier_limits(tier)

    return {
        "daily_requests": {
            "used": user.daily_requests or 0,
            "limit": limits["daily_requests"],
            "remaining": max(0, limits["daily_requests"] - (user.daily_requests or 0)),
        },
        "last_request_date": user.last_request_date,
        "tier": tier.value,
        "tier_display_name": TIER_DETAILS[tier]["display_name"],
    }


@router.post("/reset-api-key/{provider}")
async def reset_api_key(
    provider: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Reset (remove) an API key configuration."""
    if provider not in ["openai", "perplexity", "newsapi", "eodhd"]:
        raise HTTPException(status_code=400, detail="Invalid provider")

    user = await db.get(DBUser, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    current_prefs = user.preferences or {}
    api_keys_status = current_prefs.get("api_keys", {})
    api_keys_status[f"{provider}_configured"] = False
    current_prefs["api_keys"] = api_keys_status
    user.preferences = current_prefs

    await db.flush()

    logger.info("api_key_reset", user_id=str(current_user.id)[:8], provider=provider)
    return {"message": f"{provider} API key configuration removed"}
