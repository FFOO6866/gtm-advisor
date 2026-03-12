"""Add GTM-relevant financial fields to financial snapshots and listed companies

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-03-12 10:00:00.000000

Adds operational detail columns to company_financial_snapshots (cost_of_revenue,
selling_general_administrative, research_development, operating_income,
interest_expense, depreciation_amortization, sga_to_revenue, rnd_to_revenue,
operating_margin) and ESG/analyst consensus columns to listed_companies
(esg_score, esg_environment, esg_social, esg_governance, analyst_rating,
analyst_target_price, analyst_count).

All new columns are nullable — safe to add to existing tables without backfill.
Data is populated on the next EODHD sync run.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g7h8i9j0k1l2"
down_revision: str | Sequence[str] | None = "f6g7h8i9j0k1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- company_financial_snapshots: operational detail ---
    op.add_column(
        "company_financial_snapshots",
        sa.Column("cost_of_revenue", sa.Float(), nullable=True),
    )
    op.add_column(
        "company_financial_snapshots",
        sa.Column("selling_general_administrative", sa.Float(), nullable=True),
    )
    op.add_column(
        "company_financial_snapshots",
        sa.Column("research_development", sa.Float(), nullable=True),
    )
    op.add_column(
        "company_financial_snapshots",
        sa.Column("operating_income", sa.Float(), nullable=True),
    )
    op.add_column(
        "company_financial_snapshots",
        sa.Column("interest_expense", sa.Float(), nullable=True),
    )
    op.add_column(
        "company_financial_snapshots",
        sa.Column("depreciation_amortization", sa.Float(), nullable=True),
    )
    op.add_column(
        "company_financial_snapshots",
        sa.Column("sga_to_revenue", sa.Float(), nullable=True),
    )
    op.add_column(
        "company_financial_snapshots",
        sa.Column("rnd_to_revenue", sa.Float(), nullable=True),
    )
    op.add_column(
        "company_financial_snapshots",
        sa.Column("operating_margin", sa.Float(), nullable=True),
    )

    # --- listed_companies: ESG scores ---
    op.add_column(
        "listed_companies",
        sa.Column("esg_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "listed_companies",
        sa.Column("esg_environment", sa.Float(), nullable=True),
    )
    op.add_column(
        "listed_companies",
        sa.Column("esg_social", sa.Float(), nullable=True),
    )
    op.add_column(
        "listed_companies",
        sa.Column("esg_governance", sa.Float(), nullable=True),
    )

    # --- listed_companies: analyst consensus ---
    op.add_column(
        "listed_companies",
        sa.Column("analyst_rating", sa.String(20), nullable=True),
    )
    op.add_column(
        "listed_companies",
        sa.Column("analyst_target_price", sa.Float(), nullable=True),
    )
    op.add_column(
        "listed_companies",
        sa.Column("analyst_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    # company_financial_snapshots
    op.drop_column("company_financial_snapshots", "operating_margin")
    op.drop_column("company_financial_snapshots", "rnd_to_revenue")
    op.drop_column("company_financial_snapshots", "sga_to_revenue")
    op.drop_column("company_financial_snapshots", "depreciation_amortization")
    op.drop_column("company_financial_snapshots", "interest_expense")
    op.drop_column("company_financial_snapshots", "operating_income")
    op.drop_column("company_financial_snapshots", "research_development")
    op.drop_column("company_financial_snapshots", "selling_general_administrative")
    op.drop_column("company_financial_snapshots", "cost_of_revenue")

    # listed_companies
    op.drop_column("listed_companies", "analyst_count")
    op.drop_column("listed_companies", "analyst_target_price")
    op.drop_column("listed_companies", "analyst_rating")
    op.drop_column("listed_companies", "esg_governance")
    op.drop_column("listed_companies", "esg_social")
    op.drop_column("listed_companies", "esg_environment")
    op.drop_column("listed_companies", "esg_score")
