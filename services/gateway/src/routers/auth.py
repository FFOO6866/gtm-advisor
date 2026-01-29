"""Authentication router for GTM Advisor Gateway.

Provides endpoints for:
- User registration
- User login
- Token refresh
- Current user info
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from ..auth.dependencies import (
    get_current_active_user,
    get_user_by_email,
    save_user,
)
from ..auth.models import (
    LoginRequest,
    RefreshRequest,
    SubscriptionTier,
    Token,
    User,
    UserCreate,
    UserInDB,
)
from ..auth.utils import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)

logger = structlog.get_logger()

router = APIRouter()


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate) -> User:
    """
    Register a new user account.

    New users start on the FREE tier with limited access.
    """
    # Check if user already exists
    existing_user = get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    user = UserInDB(
        email=user_data.email,
        full_name=user_data.full_name,
        company_name=user_data.company_name,
        hashed_password=get_password_hash(user_data.password),
        tier=SubscriptionTier.FREE,
        is_active=True,
    )

    save_user(user)

    logger.info("user_registered", email=user.email, tier=user.tier.value)

    return User(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        company_name=user.company_name,
        tier=user.tier,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/login", response_model=Token)
async def login(credentials: LoginRequest) -> Token:
    """
    Authenticate user and return JWT tokens.

    Returns access token (30 min) and refresh token (7 days).
    """
    user = get_user_by_email(credentials.email)

    if not user or not verify_password(credentials.password, user.hashed_password):
        logger.warning("login_failed", email=credentials.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Create tokens
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        tier=user.tier,
    )
    refresh_token = create_refresh_token(
        user_id=user.id,
        email=user.email,
        tier=user.tier,
    )

    logger.info("user_logged_in", email=user.email, tier=user.tier.value)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(request: RefreshRequest) -> Token:
    """
    Refresh access token using a valid refresh token.

    Returns new access and refresh tokens.
    """
    token_data = decode_token(request.refresh_token, token_type="refresh")

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify user still exists and is active
    user = get_user_by_email(token_data.email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Create new tokens
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        tier=user.tier,
    )
    new_refresh_token = create_refresh_token(
        user_id=user.id,
        email=user.email,
        tier=user.tier,
    )

    logger.info("token_refreshed", email=user.email)

    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=User)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Get information about the currently authenticated user."""
    return current_user


@router.post("/me/upgrade-tier")
async def upgrade_tier(
    tier: SubscriptionTier,
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Upgrade user subscription tier.

    Note: In production, this would integrate with payment processing.
    For now, this is a direct tier update for testing.
    """
    user = get_user_by_email(current_user.email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update tier
    user.tier = tier
    save_user(user)

    logger.info("tier_upgraded", email=user.email, new_tier=tier.value)

    return User(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        company_name=user.company_name,
        tier=user.tier,
        is_active=user.is_active,
        created_at=user.created_at,
    )
