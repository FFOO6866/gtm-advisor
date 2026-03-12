"""Database session management for GTM Advisor.

Provides async database connections using SQLAlchemy 2.0 async API.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

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
    """Get or create the async database engine.

    In development, falls back to a local SQLite file (gtm_dev.db) when
    GTM_POSTGRES_URL is not configured.
    """
    global _engine
    if _engine is None:
        config = get_config()
        database_url = config.postgres_url

        if not database_url:
            if config.is_production:
                raise RuntimeError(
                    "Database URL not configured. Set GTM_POSTGRES_URL environment variable."
                )
            # Development fallback: local SQLite file
            database_url = "sqlite+aiosqlite:///./gtm_dev.db"

        # Convert postgresql:// to postgresql+asyncpg://
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        is_sqlite = database_url.startswith("sqlite")
        engine_kwargs: dict = {"echo": config.is_development}
        if is_sqlite:
            # SQLite: set busy_timeout so concurrent writers wait instead of failing immediately
            engine_kwargs["connect_args"] = {"timeout": 30}
        else:
            # Connection pool settings not supported by SQLite
            engine_kwargs.update({"pool_size": 5, "max_overflow": 10, "pool_pre_ping": True})

        _engine = create_async_engine(database_url, **engine_kwargs)
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


@asynccontextmanager
async def async_session_factory() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session for use in background tasks.

    This is an async context manager for use outside of FastAPI's dependency injection.

    Usage:
        async with async_session_factory() as db:
            user = await db.get(User, user_id)
            await db.commit()
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
