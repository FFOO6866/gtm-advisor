"""Database session management for GTM Advisor.

Provides async database connections using SQLAlchemy 2.0 async API.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from packages.core.src.config import get_config

from .models import Base

# Engine will be created lazily
_engine = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        config = get_config()
        database_url = config.postgres_url

        if not database_url:
            raise RuntimeError(
                "Database URL not configured. Set GTM_POSTGRES_URL environment variable."
            )

        # Convert postgresql:// to postgresql+asyncpg://
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        _engine = create_async_engine(
            database_url,
            echo=config.is_development,  # Log SQL in dev
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before use
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the async session factory."""
    global AsyncSessionLocal
    if AsyncSessionLocal is None:
        engine = get_engine()
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return AsyncSessionLocal


async def init_db() -> None:
    """Initialize database tables.

    Creates all tables if they don't exist.
    In production, use Alembic migrations instead.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    global _engine, AsyncSessionLocal
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        AsyncSessionLocal = None


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session.

    Usage:
        async with get_db() as db:
            user = await db.get(User, user_id)
            ...
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Usage:
        @router.get("/users/{user_id}")
        async def get_user(user_id: UUID, db: AsyncSession = Depends(get_db_session)):
            ...
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
