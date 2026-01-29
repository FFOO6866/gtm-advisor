"""FastAPI dependencies for authentication and authorization."""

from typing import Callable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .models import SubscriptionTier, TokenData, User, UserInDB
from .utils import decode_token

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)

# In-memory user store (will be replaced with database)
# This is a temporary solution for MVP
_users_db: dict[str, UserInDB] = {}


def get_user_by_email(email: str) -> Optional[UserInDB]:
    """Get user by email from database."""
    return _users_db.get(email)


def get_user_by_id(user_id: str) -> Optional[UserInDB]:
    """Get user by ID from database."""
    for user in _users_db.values():
        if str(user.id) == user_id:
            return user
    return None


def save_user(user: UserInDB) -> None:
    """Save user to database."""
    _users_db[user.email] = user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[User]:
    """
    Get the current user from the JWT token.

    Returns None if no token provided (for optional auth).
    Raises 401 if token is invalid.
    """
    if credentials is None:
        return None

    token_data = decode_token(credentials.credentials, token_type="access")

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(str(token_data.user_id))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return User(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        company_name=user.company_name,
        tier=user.tier,
        is_active=user.is_active,
        created_at=user.created_at,
        daily_requests=user.daily_requests,
        last_request_date=user.last_request_date,
    )


async def get_current_active_user(
    current_user: Optional[User] = Depends(get_current_user),
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
