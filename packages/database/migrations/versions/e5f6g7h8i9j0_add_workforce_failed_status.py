"""Add FAILED status to WorkforceStatus enum

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-03-11 03:00:00.000000

Adds WorkforceStatus.FAILED so the workforce design background task can
signal to the frontend when agent.run() raises an exception, making the
DRAFT vs FAILED distinction visible to users.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6g7h8i9j0"
down_revision: str | Sequence[str] | None = "d4e5f6g7h8i9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL requires ALTER TYPE to add new enum values.
    # SQLite does not enforce enum constraints, so the migration is a no-op there.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE workforcestatus ADD VALUE IF NOT EXISTS 'failed'")


def downgrade() -> None:
    # Removing an enum value from PostgreSQL requires recreating the type,
    # which is non-trivial. We leave this as a no-op for safety.
    pass
