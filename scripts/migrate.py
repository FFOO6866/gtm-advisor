#!/usr/bin/env python3
"""Database migration script.

Uses Alembic to manage database schema migrations.

Usage:
    # Upgrade to latest
    uv run python scripts/migrate.py upgrade

    # Downgrade one version
    uv run python scripts/migrate.py downgrade

    # Show current revision
    uv run python scripts/migrate.py current

    # Create new migration
    uv run python scripts/migrate.py create "description of changes"
"""

import subprocess
import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


def run_alembic(*args: str) -> int:
    """Run alembic command with proper configuration."""
    cmd = ["uv", "run", "alembic", *args]
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/migrate.py <command> [args]")
        print("")
        print("Commands:")
        print("  upgrade [revision]  - Upgrade to revision (default: head)")
        print("  downgrade [revision] - Downgrade to revision (default: -1)")
        print("  current             - Show current revision")
        print("  history             - Show migration history")
        print("  create <message>    - Create new migration")
        sys.exit(1)

    command = sys.argv[1]

    if command == "upgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "head"
        print(f"Upgrading database to {revision}...")
        sys.exit(run_alembic("upgrade", revision))

    elif command == "downgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "-1"
        print(f"Downgrading database to {revision}...")
        sys.exit(run_alembic("downgrade", revision))

    elif command == "current":
        print("Current database revision:")
        sys.exit(run_alembic("current"))

    elif command == "history":
        print("Migration history:")
        sys.exit(run_alembic("history", "--verbose"))

    elif command == "create":
        if len(sys.argv) < 3:
            print("Error: Migration message required")
            print("Usage: python scripts/migrate.py create 'description'")
            sys.exit(1)
        message = sys.argv[2]
        print(f"Creating migration: {message}")
        sys.exit(run_alembic("revision", "--autogenerate", "-m", message))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
