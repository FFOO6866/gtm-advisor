"""Authentication router for GTM Advisor Gateway.

Provides endpoints for:
- User registration
- User login
- Token refresh
- Current user info
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import SubscriptionTier
from packages.database.src.session import get_db_session

from ..auth.dependencies import (
    create_user,
    db_user_to_api_user,
    get_current_active_user,
    get_user_by_email,
    get_user_by_id,
)
from ..auth.models import (
    LoginRequest,
    RefreshRequest,
    Token,
    User,
    UserCreate,
)
from ..auth.utils import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    is_token_blacklisted,
    verify_password,
)
from ..middleware.auth import invalidate_user_cache

logger = structlog.get_logger()

router = APIRouter()


class LogoutRequest(BaseModel):
    """Logout request that can include refresh token."""

    refresh_token: str | None = None


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """
    Register a new user account.

    New users start on the FREE tier with limited access.
    """
    # Check if user already exists
    existing_user = await get_user_by_email(user_data.email, db)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user in database
    db_user = await create_user(
        email=user_data.email,
        full_name=user_data.full_name,
        company_name=user_data.company_name,
        password=user_data.password,
        db=db,
        tier=SubscriptionTier.FREE,
    )

    await db.commit()

    logger.info("user_registered", email=db_user.email, tier=db_user.tier.value)

    return db_user_to_api_user(db_user)


@router.post("/login", response_model=Token)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Token:
    """
    Authenticate user and return JWT tokens.

    Returns access token (30 min) and refresh token (7 days).
    """
    db_user = await get_user_by_email(credentials.email, db)

    if not db_user or not verify_password(credentials.password, db_user.hashed_password):
        logger.warning("login_failed", email=credentials.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Create tokens
    access_token = create_access_token(
        user_id=db_user.id,
        email=db_user.email,
        tier=db_user.tier,
    )
    refresh_token = create_refresh_token(
        user_id=db_user.id,
        email=db_user.email,
        tier=db_user.tier,
    )

    logger.info("user_logged_in", email=db_user.email, tier=db_user.tier.value)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Token:
    """
    Refresh access token using a valid refresh token.

    Returns new access and refresh tokens.
    """
    # Check if refresh token is blacklisted (logged out)
    if await is_token_blacklisted(request.refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = decode_token(request.refresh_token, token_type="refresh")

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify user still exists and is active
    db_user = await get_user_by_email(token_data.email, db)

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Create new tokens with CURRENT tier from database (not from old token)
    access_token = create_access_token(
        user_id=db_user.id,
        email=db_user.email,
        tier=db_user.tier,  # Use current tier from database
    )
    new_refresh_token = create_refresh_token(
        user_id=db_user.id,
        email=db_user.email,
        tier=db_user.tier,
    )

    logger.info("token_refreshed", email=db_user.email)

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
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """
    Upgrade user subscription tier.

    Note: In production, this would integrate with payment processing.
    For now, this is a direct tier update for testing.
    """
    db_user = await get_user_by_id(str(current_user.id), db)

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update tier
    db_user.tier = tier

    # Invalidate user cache so next request gets fresh tier from database
    await invalidate_user_cache(str(current_user.id))

    logger.info("tier_upgraded", user_id=str(current_user.id)[:8], new_tier=tier.value)

    return db_user_to_api_user(db_user)


# Security scheme for extracting bearer token
security = HTTPBearer()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    body: LogoutRequest | None = None,
) -> None:
    """
    Logout user by blacklisting their tokens.

    Blacklists the access token from the Authorization header.
    Optionally blacklists the refresh token if provided in the body.

    Tokens remain blacklisted until they would naturally expire.
    """
    access_token = credentials.credentials

    # Blacklist the access token
    access_blacklisted = await blacklist_token(access_token)

    if not access_blacklisted:
        logger.warning("logout_access_token_failed")

    # Optionally blacklist refresh token if provided
    if body and body.refresh_token and not await is_token_blacklisted(body.refresh_token):
        refresh_blacklisted = await blacklist_token(body.refresh_token)
        if not refresh_blacklisted:
            logger.warning("logout_refresh_token_failed")

    logger.info("user_logged_out")
