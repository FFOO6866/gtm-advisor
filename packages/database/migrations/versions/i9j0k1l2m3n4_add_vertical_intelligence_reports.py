"""Add vertical_intelligence_reports table

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-03-16 10:00:00.000000

Stores synthesized per-vertical intelligence reports aggregating
market data, trends, competitive dynamics, financial pulse, and
GTM implications.
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
    op.create_table(
        "vertical_intelligence_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vertical_id", sa.Uuid(), nullable=False),
        sa.Column("report_period", sa.String(20), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("market_overview", sa.JSON(), nullable=True, server_default="{}"),
        sa.Column("key_trends", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("competitive_dynamics", sa.JSON(), nullable=True, server_default="{}"),
        sa.Column("financial_pulse", sa.JSON(), nullable=True, server_default="{}"),
        sa.Column("signal_digest", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("executive_movements", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("regulatory_environment", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("gtm_implications", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("data_sources", sa.JSON(), nullable=True, server_default="{}"),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["vertical_id"], ["market_verticals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vertical_intel_report_current", "vertical_intelligence_reports", ["vertical_id", "is_current"])


def downgrade() -> None:
    op.drop_index("ix_vertical_intel_report_current", "vertical_intelligence_reports")
    op.drop_table("vertical_intelligence_reports")
