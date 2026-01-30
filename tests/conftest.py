"""Pytest configuration and fixtures for GTM Advisor tests."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.database.src.models import Base, Company, SubscriptionTier
from packages.database.src.models import User as DBUser

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async engine for tests."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for tests."""
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> DBUser:
    """Create a test user."""
    from services.gateway.src.auth.utils import get_password_hash

    user = DBUser(
        id=uuid4(),
        email="test@example.com",
        full_name="Test User",
        company_name="Test Company",
        hashed_password=get_password_hash("password123"),
        tier=SubscriptionTier.FREE,
        is_active=True,
        daily_requests=0,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_company(db_session: AsyncSession, test_user: DBUser) -> Company:
    """Create a test company owned by test_user."""
    company = Company(
        id=uuid4(),
        name="Test Company Ltd",
        owner_id=test_user.id,
        industry="Technology",
        description="AI-powered solutions for Singapore SMEs",
    )
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return company


@pytest_asyncio.fixture
async def unowned_company(db_session: AsyncSession) -> Company:
    """Create an unowned company (MVP mode - public access)."""
    company = Company(
        id=uuid4(),
        name="Public Company Ltd",
        owner_id=None,  # Unowned - public access
        industry="Technology",
        description="Public access company",
    )
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return company


@pytest.fixture
def test_access_token(test_user: DBUser) -> str:
    """Generate a test access token."""
    from services.gateway.src.auth.utils import create_access_token

    return create_access_token(
        user_id=test_user.id,
        email=test_user.email,
        tier=test_user.tier,
    )


@pytest.fixture
def test_refresh_token(test_user: DBUser) -> str:
    """Generate a test refresh token."""
    from services.gateway.src.auth.utils import create_refresh_token

    return create_refresh_token(
        user_id=test_user.id,
        email=test_user.email,
        tier=test_user.tier,
    )


@pytest.fixture
def expired_access_token(test_user: DBUser) -> str:
    """Generate an expired access token."""
    from services.gateway.src.auth.utils import create_access_token

    return create_access_token(
        user_id=test_user.id,
        email=test_user.email,
        tier=test_user.tier,
        expires_delta=timedelta(seconds=-1),  # Already expired
    )


@pytest.fixture
def auth_headers(test_access_token: str) -> dict[str, str]:
    """Generate auth headers with test token."""
    return {"Authorization": f"Bearer {test_access_token}"}
