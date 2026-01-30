"""Authentication module for GTM Advisor Gateway."""

from packages.database.src.models import SubscriptionTier

from .dependencies import get_current_active_user, get_current_user, require_tier
from .models import Token, TokenData, User, UserCreate, UserInDB
from .utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)

__all__ = [
    # Models
    "User",
    "UserCreate",
    "UserInDB",
    "Token",
    "TokenData",
    "SubscriptionTier",
    # Utils
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    # Dependencies
    "get_current_user",
    "get_current_active_user",
    "require_tier",
]
