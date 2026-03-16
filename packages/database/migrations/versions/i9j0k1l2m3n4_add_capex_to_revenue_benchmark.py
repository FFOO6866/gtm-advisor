"""Add capex_to_revenue benchmark distribution to vertical_benchmarks

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-03-16 12:00:00.000000

Adds capex_to_revenue JSON column to vertical_benchmarks for capex
intensity benchmarking. Stores {p25, p50, p75, p90, mean, n}.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i9j0k1l2m3n4"
down_revision: str | Sequence[str] | None = "h8i9j0k1l2m3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vertical_benchmarks",
        sa.Column("capex_to_revenue", sa.JSON(), nullable=True, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("vertical_benchmarks", "capex_to_revenue")
