"""Authentication module for GTM Advisor Gateway."""

from .models import User, UserCreate, UserInDB, Token, TokenData, SubscriptionTier
from .utils import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from .dependencies import get_current_user, get_current_active_user, require_tier

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
