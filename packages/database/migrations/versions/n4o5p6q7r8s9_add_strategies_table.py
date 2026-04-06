"""Add strategies table and strategy_id FK to campaigns

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-03-18 00:00:00.000000

Implements the Strategy layer:
  Insights → Strategy (human gate) → Campaigns → Execute → Monitor

Changes:
- CREATE TABLE strategies (generic strategic initiatives, AI-proposed / user-approved)
- ALTER TABLE campaigns ADD COLUMN strategy_id UUID REFERENCES strategies ON DELETE SET NULL
- CREATE INDEX ix_campaigns_strategy_id ON campaigns (strategy_id)

The strategies table uses two new enum types:
  strategy_status:   proposed | approved | rejected | in_progress | completed | revised
  strategy_priority: high | medium | low

SQLite note: SQLite does not use CREATE TYPE; SQLAlchemy emits VARCHAR for Enum columns
on SQLite, so the upgrade() below uses server_default strings rather than enum casts.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "n4o5p6q7r8s9"
down_revision: str | Sequence[str] | None = "m3n4o5p6q7r8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL: create enum types first
    # (SQLite auto-handles enums as VARCHAR — no CREATE TYPE needed)
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute(
            "CREATE TYPE strategy_status AS ENUM "
            "('proposed', 'approved', 'rejected', 'in_progress', 'completed', 'revised')"
        )
        op.execute(
            "CREATE TYPE strategy_priority AS ENUM ('high', 'medium', 'low')"
        )

    status_col = (
        sa.Column(
            "status",
            postgresql.ENUM(
                "proposed", "approved", "rejected", "in_progress", "completed", "revised",
                name="strategy_status",
                create_type=False,
            ),
            nullable=False,
            server_default="proposed",
        )
        if is_postgres
        else sa.Column("status", sa.String(20), nullable=False, server_default="proposed")
    )

    priority_col = (
        sa.Column(
            "priority",
            postgresql.ENUM(
                "high", "medium", "low",
                name="strategy_priority",
                create_type=False,
            ),
            nullable=False,
            server_default="medium",
        )
        if is_postgres
        else sa.Column("priority", sa.String(10), nullable=False, server_default="medium")
    )

    op.create_table(
        "strategies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
            primary_key=True,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "roadmap_id",
            postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
            sa.ForeignKey("gtm_roadmaps.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("insight_sources", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("expected_outcome", sa.String(500), nullable=False),
        sa.Column("success_metrics", sa.JSON, nullable=False, server_default="[]"),
        priority_col,
        sa.Column("estimated_timeline", sa.String(100), nullable=True),
        sa.Column("target_segment", sa.String(300), nullable=True),
        status_col,
        sa.Column("user_notes", sa.Text, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_strategies_company_id", "strategies", ["company_id"])
    op.create_index("ix_strategies_status", "strategies", ["status"])
    op.create_index("ix_strategies_roadmap_id", "strategies", ["roadmap_id"])

    # Add strategy_id FK to campaigns
    op.add_column(
        "campaigns",
        sa.Column(
            "strategy_id",
            postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
            sa.ForeignKey("strategies.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_campaigns_strategy_id", "campaigns", ["strategy_id"])


def downgrade() -> None:
    op.drop_index("ix_campaigns_strategy_id", table_name="campaigns")
    op.drop_column("campaigns", "strategy_id")

    op.drop_index("ix_strategies_roadmap_id", table_name="strategies")
    op.drop_index("ix_strategies_status", table_name="strategies")
    op.drop_index("ix_strategies_company_id", table_name="strategies")
    op.drop_table("strategies")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS strategy_priority")
        op.execute("DROP TYPE IF EXISTS strategy_status")
