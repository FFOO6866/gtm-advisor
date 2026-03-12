"""Add context_sources column to companies table

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-03-11 12:00:00.000000

Replaces the single document_text Text column with context_sources JSON, which
stores a list of {type, name, text, chars, added_at} dicts — one entry per
uploaded document or website scrape. Agents receive all sources joined into a
single additional_context string, giving full persistent context across re-runs.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6g7h8i9j0k1"
down_revision: str | Sequence[str] | None = "e5f6g7h8i9j0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("context_sources", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "context_sources")
