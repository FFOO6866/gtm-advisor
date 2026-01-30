"""Authentication utilities for password hashing and JWT handling."""

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import bcrypt
from jose import JWTError, jwt

from packages.core.src.config import get_config
from packages.database.src.models import SubscriptionTier

from .models import TokenData

logger = logging.getLogger(__name__)

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
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token with unique JTI for blacklisting support."""
    config = get_config()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(user_id),
        "email": email,
        "tier": tier.value,
        "exp": expire,
        "type": "access",
        "jti": str(uuid4()),  # Unique token identifier for blacklisting
    }

    return jwt.encode(to_encode, config.jwt_secret, algorithm=ALGORITHM)


def create_refresh_token(
    user_id: UUID,
    email: str,
    tier: SubscriptionTier,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT refresh token with unique JTI for blacklisting support."""
    config = get_config()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": str(user_id),
        "email": email,
        "tier": tier.value,
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid4()),  # Unique token identifier for blacklisting
    }

    return jwt.encode(to_encode, config.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str, token_type: str = "access") -> TokenData | None:
    """
    Decode and validate a JWT token.

    Note: This does NOT check the blacklist. Use is_token_blacklisted() for that.

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
        jti = payload.get("jti")

        if not all([user_id, email, tier, exp]):
            return None

        try:
            return TokenData(
                user_id=UUID(user_id),
                email=email,
                tier=SubscriptionTier(tier),
                exp=datetime.fromtimestamp(exp, tz=UTC),
                jti=jti,
            )
        except ValueError:
            # Invalid tier value
            return None
    except JWTError:
        return None


def get_token_jti(token: str) -> str | None:
    """Extract JTI from token without full validation.

    For tokens without JTI, returns a hash of the token as fallback.
    """
    config = get_config()
    try:
        payload = jwt.decode(token, config.jwt_secret, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        if jti:
            return jti
        # Fallback: hash the token for tokens without JTI
        return hashlib.sha256(token.encode()).hexdigest()[:32]
    except JWTError:
        return None


async def is_token_blacklisted(token: str) -> bool:
    """Check if a token is blacklisted.

    Args:
        token: The JWT token string

    Returns:
        True if blacklisted, False otherwise
    """
    jti = get_token_jti(token)
    if not jti:
        return False  # Invalid token will be rejected elsewhere

    try:
        from ..cache import get_token_blacklist

        blacklist = get_token_blacklist()
        return await blacklist.is_blacklisted(jti)
    except RuntimeError:
        # Cache not initialized - can't check blacklist
        logger.warning("Token blacklist not available")
        return False


async def blacklist_token(token: str, ttl_seconds: int | None = None) -> bool:
    """Add a token to the blacklist.

    Args:
        token: The JWT token string
        ttl_seconds: Time-to-live in seconds. If None, uses remaining token lifetime.

    Returns:
        True if successfully blacklisted, False otherwise
    """
    token_data = decode_token(token, token_type="access")
    if not token_data:
        # Try refresh token
        token_data = decode_token(token, token_type="refresh")

    if not token_data:
        return False

    jti = token_data.jti
    if not jti:
        # Fallback for tokens without JTI
        jti = hashlib.sha256(token.encode()).hexdigest()[:32]

    # Calculate TTL from token expiration if not provided
    if ttl_seconds is None:
        remaining = token_data.exp - datetime.now(UTC)
        ttl_seconds = max(int(remaining.total_seconds()), 1)

    try:
        from ..cache import get_token_blacklist

        blacklist = get_token_blacklist()
        await blacklist.add(jti, ttl_seconds)
        logger.info("Token blacklisted", jti=jti[:8])
        return True
    except RuntimeError:
        logger.error("Token blacklist not available - logout may not be effective")
        return False
    except Exception as e:
        logger.error("Failed to blacklist token: %s", str(e))
        return False
