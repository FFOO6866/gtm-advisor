#!/usr/bin/env python3
"""Initialize database tables.

This script creates all database tables defined in the models.
Run this before starting the application for the first time.

Usage:
    uv run python scripts/init_db.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from packages.database.src.session import close_db, init_db


async def main():
    """Initialize the database."""
    print("Initializing database tables...")
    try:
        await init_db()
        print("Database tables created successfully!")
    except Exception as e:
        print(f"Error creating database tables: {e}")
        raise
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
