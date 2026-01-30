"""Integration tests for company access control."""

from uuid import uuid4

import pytest

from packages.database.src.models import Company, SubscriptionTier
from packages.database.src.models import User as DBUser


class TestCompanyAccess:
    """Tests for company access validation."""

    @pytest.mark.asyncio
    async def test_access_unowned_company_without_auth(self, db_session, unowned_company):
        """Unowned company should be accessible without authentication (MVP mode)."""
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
                # Access unowned company's competitors without auth
                response = await client.get(f"/api/v1/companies/{unowned_company.id}/competitors")

            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_access_owned_company_without_auth_fails(self, db_session, test_company):
        """Owned company should NOT be accessible without authentication."""
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
                # Try to access owned company's competitors without auth
                response = await client.get(f"/api/v1/companies/{test_company.id}/competitors")

            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_access_own_company_with_auth(
        self, db_session, test_user, test_company, test_access_token
    ):
        """Owner should be able to access their own company."""
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
                    f"/api/v1/companies/{test_company.id}/competitors",
                    headers={"Authorization": f"Bearer {test_access_token}"},
                )

            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_access_other_user_company_fails(self, db_session, test_access_token):
        """User should NOT be able to access another user's company."""
        from httpx import ASGITransport, AsyncClient

        from packages.database.src.session import get_db_session
        from services.gateway.src.auth.utils import get_password_hash
        from services.gateway.src.main import app

        # Create another user and their company
        other_user = DBUser(
            id=uuid4(),
            email="other@example.com",
            full_name="Other User",
            hashed_password=get_password_hash("password"),
            tier=SubscriptionTier.FREE,
            is_active=True,
        )
        db_session.add(other_user)

        other_company = Company(
            id=uuid4(),
            name="Other Company Ltd",
            owner_id=other_user.id,
            industry="Technology",
            description="Another company",
        )
        db_session.add(other_company)
        await db_session.commit()

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                # Try to access other user's company with our token
                response = await client.get(
                    f"/api/v1/companies/{other_company.id}/competitors",
                    headers={"Authorization": f"Bearer {test_access_token}"},
                )

            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_access_nonexistent_company(self, db_session, test_access_token):
        """Should return 404 for non-existent company."""
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
                    f"/api/v1/companies/{uuid4()}/competitors",
                    headers={"Authorization": f"Bearer {test_access_token}"},
                )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestCompetitorsCRUD:
    """Tests for competitors CRUD operations with authorization."""

    @pytest.mark.asyncio
    async def test_create_competitor_authorized(
        self, db_session, test_user, test_company, test_access_token
    ):
        """Owner should be able to create competitor for their company."""
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
                    f"/api/v1/companies/{test_company.id}/competitors",
                    headers={"Authorization": f"Bearer {test_access_token}"},
                    json={
                        "name": "Competitor Inc",
                        "website": "https://competitor.com",
                        "threat_level": "medium",
                    },
                )

            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "Competitor Inc"
            assert data["threat_level"] == "medium"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_competitor_unauthorized(self, db_session, test_company):
        """Unauthenticated user should NOT be able to create competitor for owned company."""
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
                    f"/api/v1/companies/{test_company.id}/competitors",
                    json={
                        "name": "Competitor Inc",
                        "threat_level": "medium",
                    },
                )

            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()


class TestSettingsAccess:
    """Tests for settings endpoint access control."""

    @pytest.mark.asyncio
    async def test_get_settings_authenticated(self, db_session, test_user, test_access_token):
        """Authenticated user should be able to get their settings."""
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
                    "/api/v1/settings/me",
                    headers={"Authorization": f"Bearer {test_access_token}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["email"] == test_user.email
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_settings_unauthenticated(self, db_session):
        """Unauthenticated user should NOT be able to get settings."""
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
                response = await client.get("/api/v1/settings/me")

            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()
