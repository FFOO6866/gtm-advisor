"""Add SG&A, R&D, and operating margin benchmark distributions to vertical_benchmarks

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-03-12 12:00:00.000000

Adds three new JSON columns to vertical_benchmarks for GTM-relevant
operational benchmarks: sga_to_revenue, rnd_to_revenue, operating_margin_dist.
Each stores a percentile distribution dict {p25, p50, p75, p90, mean, n}.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h8i9j0k1l2m3"
down_revision: str | Sequence[str] | None = "g7h8i9j0k1l2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vertical_benchmarks",
        sa.Column("sga_to_revenue", sa.JSON(), nullable=True, server_default="{}"),
    )
    op.add_column(
        "vertical_benchmarks",
        sa.Column("rnd_to_revenue", sa.JSON(), nullable=True, server_default="{}"),
    )
    op.add_column(
        "vertical_benchmarks",
        sa.Column("operating_margin_dist", sa.JSON(), nullable=True, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("vertical_benchmarks", "operating_margin_dist")
    op.drop_column("vertical_benchmarks", "rnd_to_revenue")
    op.drop_column("vertical_benchmarks", "sga_to_revenue")
