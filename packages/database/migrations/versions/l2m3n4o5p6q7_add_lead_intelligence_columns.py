"""Add pain_points, trigger_events, recommended_approach to leads table

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-03-17 12:00:00.000000

Adds intelligence columns so Lead Hunter analysis results (trigger events,
pain points, outreach angles) are persisted alongside lead contact info.
All columns default to NULL — safe to add without backfill.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l2m3n4o5p6q7"
down_revision: str | Sequence[str] | None = "k1l2m3n4o5p6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("pain_points", sa.JSON(), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("trigger_events", sa.JSON(), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("recommended_approach", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("leads", "recommended_approach")
    op.drop_column("leads", "trigger_events")
    op.drop_column("leads", "pain_points")
