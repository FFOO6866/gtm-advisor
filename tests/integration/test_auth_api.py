"""Integration tests for authentication API endpoints."""

from uuid import uuid4

import pytest

from packages.database.src.models import SubscriptionTier
from packages.database.src.models import User as DBUser


class TestRegisterEndpoint:
    """Tests for POST /api/v1/auth/register."""

    @pytest.mark.asyncio
    async def test_register_new_user(self, db_session):
        """Should successfully register a new user."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.main import app

        # Override the database dependency
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": "newuser@example.com",
                        "full_name": "New User",
                        "company_name": "New Company",
                        "password": "securepassword123",
                    },
                )

            assert response.status_code == 201
            data = response.json()
            assert data["email"] == "newuser@example.com"
            assert data["full_name"] == "New User"
            assert data["tier"] == "free"
            assert data["is_active"] is True
            assert "id" in data
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, db_session, test_user):
        """Should reject registration with existing email."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": test_user.email,  # Existing email
                        "full_name": "Another User",
                        "password": "securepassword123",
                    },
                )

            assert response.status_code == 400
            # Error response uses 'message' key (from error handler)
            data = response.json()
            message = data.get("message") or data.get("detail", "")
            assert "already registered" in message.lower()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, db_session):
        """Should reject registration with invalid email."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": "not-an-email",
                        "full_name": "Test User",
                        "password": "securepassword123",
                    },
                )

            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_register_short_password(self, db_session):
        """Should reject registration with short password."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": "newuser@example.com",
                        "full_name": "Test User",
                        "password": "short",  # Less than 8 characters
                    },
                )

            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()


class TestLoginEndpoint:
    """Tests for POST /api/v1/auth/login."""

    @pytest.mark.asyncio
    async def test_login_success(self, db_session, test_user):
        """Should successfully login with correct credentials."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": test_user.email,
                        "password": "password123",  # From fixture
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["token_type"] == "bearer"
            assert "expires_in" in data
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, db_session, test_user):
        """Should reject login with wrong password."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": test_user.email,
                        "password": "wrongpassword",
                    },
                )

            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, db_session):
        """Should reject login for non-existent user."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": "nonexistent@example.com",
                        "password": "anypassword",
                    },
                )

            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, db_session):
        """Should reject login for inactive user."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.auth.utils import get_password_hash
        from services.gateway.src.main import app

        # Create inactive user
        inactive_user = DBUser(
            id=uuid4(),
            email="inactive@example.com",
            full_name="Inactive User",
            hashed_password=get_password_hash("password123"),
            tier=SubscriptionTier.FREE,
            is_active=False,
        )
        db_session.add(inactive_user)
        await db_session.commit()

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": "inactive@example.com",
                        "password": "password123",
                    },
                )

            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()


class TestMeEndpoint:
    """Tests for GET /api/v1/auth/me."""

    @pytest.mark.asyncio
    async def test_get_current_user(self, db_session, test_user, test_access_token):
        """Should return current user info with valid token."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {test_access_token}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["email"] == test_user.email
            assert data["full_name"] == test_user.full_name
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_current_user_no_token(self, db_session):
        """Should return 401 without token."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/auth/me")

            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, db_session):
        """Should return 401 with invalid token."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": "Bearer invalid.token.here"},
                )

            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(
        self, db_session, test_user, expired_access_token
    ):
        """Should return 401 with expired token."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {expired_access_token}"},
                )

            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()


class TestRefreshEndpoint:
    """Tests for POST /api/v1/auth/refresh."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, db_session, test_user, test_refresh_token):
        """Should return new tokens with valid refresh token."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/refresh",
                    json={"refresh_token": test_refresh_token},
                )

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["access_token"] != ""
            assert data["refresh_token"] != test_refresh_token  # New token
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_fails(self, db_session, test_user, test_access_token):
        """Should reject access token used as refresh token."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/refresh",
                    json={"refresh_token": test_access_token},
                )

            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()


class TestLogoutEndpoint:
    """Tests for POST /api/v1/auth/logout."""

    @pytest.mark.asyncio
    async def test_logout_success(self, db_session, test_user, test_access_token):
        """Should successfully logout and blacklist token."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                # Logout
                response = await client.post(
                    "/api/v1/auth/logout",
                    headers={"Authorization": f"Bearer {test_access_token}"},
                )

            assert response.status_code == 204
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_logout_requires_token(self, db_session):
        """Should require a token to logout."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/api/v1/auth/logout")

            # HTTPBearer returns 403 Forbidden when no token provided
            assert response.status_code in (401, 403)
        finally:
            app.dependency_overrides.clear()
