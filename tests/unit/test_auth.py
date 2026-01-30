"""Unit tests for authentication utilities."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from packages.database.src.models import SubscriptionTier
from services.gateway.src.auth.utils import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    get_token_jti,
    verify_password,
)


class TestPasswordHashing:
    """Tests for password hashing utilities."""

    def test_hash_password_returns_different_value(self):
        """Password hash should be different from original password."""
        password = "test_password_123"
        hashed = get_password_hash(password)
        assert hashed != password

    def test_hash_is_different_each_time(self):
        """Same password should produce different hashes (due to salt)."""
        password = "test_password_123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        assert hash1 != hash2

    def test_verify_correct_password(self):
        """Correct password should verify successfully."""
        password = "test_password_123"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        """Wrong password should fail verification."""
        password = "test_password_123"
        hashed = get_password_hash(password)
        assert verify_password("wrong_password", hashed) is False

    def test_verify_empty_password(self):
        """Empty password should fail verification."""
        password = "test_password_123"
        hashed = get_password_hash(password)
        assert verify_password("", hashed) is False


class TestAccessToken:
    """Tests for access token creation and decoding."""

    def test_create_access_token_returns_string(self):
        """Access token should be a non-empty string."""
        user_id = uuid4()
        token = create_access_token(
            user_id=user_id,
            email="test@example.com",
            tier=SubscriptionTier.FREE,
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_valid_access_token(self):
        """Valid access token should decode successfully."""
        user_id = uuid4()
        email = "test@example.com"
        tier = SubscriptionTier.TIER1

        token = create_access_token(
            user_id=user_id,
            email=email,
            tier=tier,
        )

        token_data = decode_token(token, token_type="access")

        assert token_data is not None
        assert token_data.user_id == user_id
        assert token_data.email == email
        assert token_data.tier == tier
        assert token_data.jti is not None  # JTI should be present

    def test_decode_expired_access_token(self):
        """Expired access token should return None."""
        user_id = uuid4()

        token = create_access_token(
            user_id=user_id,
            email="test@example.com",
            tier=SubscriptionTier.FREE,
            expires_delta=timedelta(seconds=-1),  # Already expired
        )

        token_data = decode_token(token, token_type="access")
        assert token_data is None

    def test_decode_access_token_as_refresh_fails(self):
        """Access token should not decode as refresh token."""
        user_id = uuid4()

        token = create_access_token(
            user_id=user_id,
            email="test@example.com",
            tier=SubscriptionTier.FREE,
        )

        # Try to decode as refresh token
        token_data = decode_token(token, token_type="refresh")
        assert token_data is None

    def test_access_token_expiration(self):
        """Access token should have correct expiration time."""
        user_id = uuid4()
        before = datetime.now(UTC)

        token = create_access_token(
            user_id=user_id,
            email="test@example.com",
            tier=SubscriptionTier.FREE,
        )

        after = datetime.now(UTC)
        token_data = decode_token(token, token_type="access")

        assert token_data is not None
        # Expiration should be approximately ACCESS_TOKEN_EXPIRE_MINUTES from now
        # Add 1 second tolerance for timing variations
        expected_min = (
            before + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES) - timedelta(seconds=1)
        )
        expected_max = after + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES) + timedelta(seconds=1)
        assert expected_min <= token_data.exp <= expected_max

    def test_access_token_custom_expiration(self):
        """Access token should respect custom expiration."""
        user_id = uuid4()
        custom_delta = timedelta(hours=2)

        token = create_access_token(
            user_id=user_id,
            email="test@example.com",
            tier=SubscriptionTier.FREE,
            expires_delta=custom_delta,
        )

        token_data = decode_token(token, token_type="access")

        assert token_data is not None
        # Should expire in approximately 2 hours
        expected = datetime.now(UTC) + custom_delta
        assert abs((token_data.exp - expected).total_seconds()) < 5


class TestRefreshToken:
    """Tests for refresh token creation and decoding."""

    def test_create_refresh_token_returns_string(self):
        """Refresh token should be a non-empty string."""
        user_id = uuid4()
        token = create_refresh_token(
            user_id=user_id,
            email="test@example.com",
            tier=SubscriptionTier.FREE,
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_valid_refresh_token(self):
        """Valid refresh token should decode successfully."""
        user_id = uuid4()
        email = "test@example.com"
        tier = SubscriptionTier.TIER2

        token = create_refresh_token(
            user_id=user_id,
            email=email,
            tier=tier,
        )

        token_data = decode_token(token, token_type="refresh")

        assert token_data is not None
        assert token_data.user_id == user_id
        assert token_data.email == email
        assert token_data.tier == tier
        assert token_data.jti is not None

    def test_decode_refresh_token_as_access_fails(self):
        """Refresh token should not decode as access token."""
        user_id = uuid4()

        token = create_refresh_token(
            user_id=user_id,
            email="test@example.com",
            tier=SubscriptionTier.FREE,
        )

        # Try to decode as access token
        token_data = decode_token(token, token_type="access")
        assert token_data is None

    def test_refresh_token_longer_expiration(self):
        """Refresh token should have longer expiration than access token."""
        user_id = uuid4()

        access_token = create_access_token(
            user_id=user_id,
            email="test@example.com",
            tier=SubscriptionTier.FREE,
        )
        refresh_token = create_refresh_token(
            user_id=user_id,
            email="test@example.com",
            tier=SubscriptionTier.FREE,
        )

        access_data = decode_token(access_token, token_type="access")
        refresh_data = decode_token(refresh_token, token_type="refresh")

        assert access_data is not None
        assert refresh_data is not None
        assert refresh_data.exp > access_data.exp


class TestTokenJTI:
    """Tests for token JTI (unique identifier) functionality."""

    def test_access_token_has_jti(self):
        """Access token should contain a JTI."""
        token = create_access_token(
            user_id=uuid4(),
            email="test@example.com",
            tier=SubscriptionTier.FREE,
        )

        jti = get_token_jti(token)
        assert jti is not None
        assert len(jti) > 0

    def test_different_tokens_have_different_jti(self):
        """Each token should have a unique JTI."""
        user_id = uuid4()

        token1 = create_access_token(
            user_id=user_id,
            email="test@example.com",
            tier=SubscriptionTier.FREE,
        )
        token2 = create_access_token(
            user_id=user_id,
            email="test@example.com",
            tier=SubscriptionTier.FREE,
        )

        jti1 = get_token_jti(token1)
        jti2 = get_token_jti(token2)

        assert jti1 != jti2

    def test_get_jti_from_invalid_token(self):
        """Getting JTI from invalid token should return None."""
        jti = get_token_jti("invalid.token.here")
        assert jti is None


class TestTokenDecodeEdgeCases:
    """Tests for edge cases in token decoding."""

    def test_decode_empty_token(self):
        """Empty token should return None."""
        token_data = decode_token("", token_type="access")
        assert token_data is None

    def test_decode_malformed_token(self):
        """Malformed token should return None."""
        token_data = decode_token("not.a.valid.jwt", token_type="access")
        assert token_data is None

    def test_decode_token_missing_claims(self):
        """Token with missing claims should return None."""
        from jose import jwt

        from packages.core.src.config import get_config

        config = get_config()

        # Create token with missing email claim
        token = jwt.encode(
            {
                "sub": str(uuid4()),
                "tier": "free",
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "type": "access",
                # Missing "email" claim
            },
            config.jwt_secret,
            algorithm=ALGORITHM,
        )

        token_data = decode_token(token, token_type="access")
        assert token_data is None

    def test_decode_token_invalid_tier(self):
        """Token with invalid tier should return None."""
        from jose import jwt

        from packages.core.src.config import get_config

        config = get_config()

        token = jwt.encode(
            {
                "sub": str(uuid4()),
                "email": "test@example.com",
                "tier": "invalid_tier",
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "type": "access",
            },
            config.jwt_secret,
            algorithm=ALGORITHM,
        )

        token_data = decode_token(token, token_type="access")
        assert token_data is None
