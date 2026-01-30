"""FastAPI dependencies for authentication and authorization.

Uses database for user storage instead of in-memory dict.
"""

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import SubscriptionTier
from packages.database.src.models import User as DBUser
from packages.database.src.session import get_db_session

from .models import User
from .utils import decode_token, get_password_hash, is_token_blacklisted

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


async def get_user_by_email(
    email: str,
    db: AsyncSession,
) -> DBUser | None:
    """Get user by email from database."""
    result = await db.execute(select(DBUser).where(DBUser.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(
    user_id: str | UUID,
    db: AsyncSession,
) -> DBUser | None:
    """Get user by ID from database."""
    if isinstance(user_id, str):
        user_id = UUID(user_id)
    return await db.get(DBUser, user_id)


async def save_user(user: DBUser, db: AsyncSession) -> None:
    """Save user to database."""
    db.add(user)
    await db.flush()


async def create_user(
    email: str,
    full_name: str,
    company_name: str | None,
    password: str,
    db: AsyncSession,
    tier: SubscriptionTier = SubscriptionTier.FREE,
) -> DBUser:
    """Create a new user in the database."""
    user = DBUser(
        email=email,
        full_name=full_name,
        company_name=company_name,
        hashed_password=get_password_hash(password),
        tier=tier,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


def db_user_to_api_user(db_user: DBUser) -> User:
    """Convert database user model to API user model."""
    return User(
        id=db_user.id,
        email=db_user.email,
        full_name=db_user.full_name,
        company_name=db_user.company_name,
        tier=db_user.tier,
        is_active=db_user.is_active,
        created_at=db_user.created_at,
        daily_requests=db_user.daily_requests or 0,
        last_request_date=db_user.last_request_date,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db_session),
) -> User | None:
    """
    Get the current user from the JWT token.

    Returns None if no token provided (for optional auth).
    Raises 401 if token is invalid or blacklisted.
    """
    if credentials is None:
        return None

    token = credentials.credentials

    # Check if token is blacklisted (logged out)
    if await is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = decode_token(token, token_type="access")

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    db_user = await get_user_by_id(str(token_data.user_id), db)

    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return db_user_to_api_user(db_user)


async def get_current_active_user(
    current_user: User | None = Depends(get_current_user),
) -> User:
    """
    Get current user and verify they are authenticated and active.

    Raises 401 if not authenticated.
    Raises 403 if user is inactive.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return current_user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db_session),
) -> User | None:
    """
    Get the current user if authenticated, None otherwise.

    Unlike get_current_active_user, this doesn't raise if not authenticated.
    Use this for endpoints that work for both authenticated and unauthenticated users.
    Blacklisted tokens are treated as unauthenticated.
    """
    if credentials is None:
        return None

    try:
        token = credentials.credentials

        # Check if token is blacklisted (logged out)
        if await is_token_blacklisted(token):
            return None

        token_data = decode_token(token, token_type="access")

        if token_data is None:
            return None

        db_user = await get_user_by_id(str(token_data.user_id), db)

        if db_user is None or not db_user.is_active:
            return None

        return db_user_to_api_user(db_user)
    except Exception:
        return None


async def validate_company_access(
    company_id: UUID,
    user: User | None,
    db: AsyncSession,
) -> None:
    """Validate user has access to a company.

    Access rules:
    - Unowned companies (owner_id=None) are accessible by anyone (MVP mode)
    - Owned companies require authentication and ownership

    Args:
        company_id: The company to check access for
        user: The current user (may be None for unauthenticated)
        db: Database session

    Raises:
        HTTPException: If company not found or access denied
    """
    from packages.database.src.models import Company

    company = await db.get(Company, company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    # Unowned companies are public (MVP mode) - anyone can access
    if company.owner_id is None:
        return

    # Company has owner - require authentication
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access this company",
        )

    # Check ownership
    if company.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this company",
        )


def require_tier(minimum_tier: SubscriptionTier) -> Callable:
    """
    Create a dependency that requires a minimum subscription tier.

    Usage:
        @router.get("/premium-feature")
        async def premium_feature(user: User = Depends(require_tier(SubscriptionTier.TIER1))):
            ...
    """
    tier_order = {
        SubscriptionTier.FREE: 0,
        SubscriptionTier.TIER1: 1,
        SubscriptionTier.TIER2: 2,
    }

    async def check_tier(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        user_tier_level = tier_order.get(current_user.tier, 0)
        required_tier_level = tier_order.get(minimum_tier, 0)

        if user_tier_level < required_tier_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires {minimum_tier.value} subscription or higher",
            )

        return current_user

    return check_tier
