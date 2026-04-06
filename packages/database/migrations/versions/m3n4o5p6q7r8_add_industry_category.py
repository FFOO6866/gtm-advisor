"""Add industry_category column to market_verticals table

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-03-18 12:00:00.000000

Adds a two-tier industry taxonomy column so verticals can be grouped into
broad industry categories (e.g. Technology, Financial Services) for filtering
and display in the dashboard. Nullable — existing rows receive NULL until
seed_verticals() is re-run.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m3n4o5p6q7r8"
down_revision: str | Sequence[str] | None = "l2m3n4o5p6q7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "market_verticals",
        sa.Column("industry_category", sa.String(100), nullable=True, index=True),
    )


def downgrade() -> None:
    op.drop_column("market_verticals", "industry_category")
