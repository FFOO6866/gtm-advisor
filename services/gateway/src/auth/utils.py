"""Authentication utilities for password hashing and JWT handling."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from packages.core.src.config import get_config

from .models import SubscriptionTier, TokenData

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    """Hash a password for storage."""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def create_access_token(
    user_id: UUID,
    email: str,
    tier: SubscriptionTier,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token."""
    config = get_config()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(user_id),
        "email": email,
        "tier": tier.value,
        "exp": expire,
        "type": "access",
    }

    return jwt.encode(to_encode, config.jwt_secret, algorithm=ALGORITHM)


def create_refresh_token(
    user_id: UUID,
    email: str,
    tier: SubscriptionTier,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT refresh token."""
    config = get_config()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": str(user_id),
        "email": email,
        "tier": tier.value,
        "exp": expire,
        "type": "refresh",
    }

    return jwt.encode(to_encode, config.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """
    Decode and validate a JWT token.

    Args:
        token: The JWT token string
        token_type: Expected token type ("access" or "refresh")

    Returns:
        TokenData if valid, None if invalid
    """
    config = get_config()

    try:
        payload = jwt.decode(token, config.jwt_secret, algorithms=[ALGORITHM])

        # Verify token type
        if payload.get("type") != token_type:
            return None

        user_id = payload.get("sub")
        email = payload.get("email")
        tier = payload.get("tier")
        exp = payload.get("exp")

        if not all([user_id, email, tier, exp]):
            return None

        return TokenData(
            user_id=UUID(user_id),
            email=email,
            tier=SubscriptionTier(tier),
            exp=datetime.fromtimestamp(exp, tz=timezone.utc),
        )
    except JWTError:
        return None
