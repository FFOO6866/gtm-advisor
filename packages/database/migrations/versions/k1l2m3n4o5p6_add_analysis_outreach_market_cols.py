"""Add outreach_sequences, content_pieces, market_sizing to analyses table

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-03-16 10:00:00.000000

Adds three nullable JSON columns to the analyses table so that outreach
sequences, content pieces, and the full raw market intelligence output are
persisted alongside the existing analysis results. All columns default to
NULL — safe to add without backfill.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k1l2m3n4o5p6"
down_revision: str | Sequence[str] | None = "j0k1l2m3n4o5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column("outreach_sequences", sa.JSON(), nullable=True),
    )
    op.add_column(
        "analyses",
        sa.Column("content_pieces", sa.JSON(), nullable=True),
    )
    op.add_column(
        "analyses",
        sa.Column("market_sizing", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analyses", "market_sizing")
    op.drop_column("analyses", "content_pieces")
    op.drop_column("analyses", "outreach_sequences")
