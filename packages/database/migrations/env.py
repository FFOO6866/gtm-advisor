"""Alembic migration environment configuration.

Supports both async and sync operations for SQLAlchemy 2.0.
Uses the same database URL as the main application (GTM_POSTGRES_URL).
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import Base metadata from models
from packages.database.src.models import Base

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target_metadata for autogenerate support
target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from environment.

    Checks these environment variables in order:
    1. GTM_POSTGRES_URL - main application config (preferred)
    2. DATABASE_URL - common convention
    3. Falls back to SQLite for local development
    """
    # Check GTM_POSTGRES_URL first (matches main app config)
    url = os.getenv("GTM_POSTGRES_URL")

    # Fall back to DATABASE_URL
    if not url:
        url = os.getenv("DATABASE_URL")

    if url:
        # Convert postgres:// to postgresql:// for SQLAlchemy 2.0
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        # Convert to async driver for migrations
        if "postgresql://" in url and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # Fall back to SQLite for local development
    return "sqlite+aiosqlite:///./gtm_advisor.db"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
