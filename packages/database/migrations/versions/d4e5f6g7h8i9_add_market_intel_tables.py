"""Add market intelligence database tables

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-03-11 02:00:00.000000

Creates 8 tables for the Singapore Market Intelligence Database:
  market_verticals             — SSIC-anchored industry vertical taxonomy (12 verticals)
  listed_companies             — SGX + overseas-listed Singapore companies
  company_financial_snapshots  — Income statement, balance sheet, cash flow per period
  vertical_benchmarks          — Precomputed percentile rankings per vertical+period
  market_articles              — RSS/news articles with embeddings for semantic search
  company_documents            — Corporate PDFs (annual reports, sustainability reports, etc.)
  document_chunks              — Text chunks from PDFs with embeddings for RAG
  company_executives           — Executive roster with news monitoring state

Also creates 3 enums:
  companylistingtype   — common_stock, reit, etf, business_trust, preferred
  financialperiodtype  — annual, quarterly
  documenttype         — annual_report, sustainability_report, earnings_release, etc.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6g7h8i9"
down_revision: str | Sequence[str] | None = "c3d4e5f6g7h8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create market intelligence tables and enums."""

    # Detect dialect — enums only created for PostgreSQL
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    uuid_type = sa.dialects.postgresql.UUID(as_uuid=True) if is_postgresql else sa.String(36)

    # --- Enums (PostgreSQL only; SQLite uses VARCHAR) ---
    if is_postgresql:
        companylistingtype_enum = sa.Enum(
            "common_stock", "reit", "etf", "business_trust", "preferred",
            name="companylistingtype",
        )
        companylistingtype_enum.create(bind, checkfirst=True)

        financialperiodtype_enum = sa.Enum(
            "annual", "quarterly",
            name="financialperiodtype",
        )
        financialperiodtype_enum.create(bind, checkfirst=True)

        documenttype_enum = sa.Enum(
            "annual_report", "sustainability_report", "earnings_release",
            "material_announcement", "press_release", "investor_presentation", "circular",
            name="documenttype",
        )
        documenttype_enum.create(bind, checkfirst=True)

    listing_type_col = (
        sa.Enum("common_stock", "reit", "etf", "business_trust", "preferred",
                name="companylistingtype", create_type=False)
        if is_postgresql else sa.String(30)
    )
    period_type_col = (
        sa.Enum("annual", "quarterly", name="financialperiodtype", create_type=False)
        if is_postgresql else sa.String(20)
    )
    doc_type_col = (
        sa.Enum(
            "annual_report", "sustainability_report", "earnings_release",
            "material_announcement", "press_release", "investor_presentation", "circular",
            name="documenttype", create_type=False,
        )
        if is_postgresql else sa.String(40)
    )

    # ---------------------------------------------------------------
    # Table 1: market_verticals
    # ---------------------------------------------------------------
    op.create_table(
        "market_verticals",
        sa.Column("id", uuid_type,
                  primary_key=True),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("ssic_sections", sa.JSON, nullable=True),
        sa.Column("ssic_codes", sa.JSON, nullable=True),
        sa.Column("gics_sectors", sa.JSON, nullable=True),
        sa.Column("keywords", sa.JSON, nullable=True),
        sa.Column("is_reit_vertical", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
    )
    op.create_index("ix_market_verticals_slug", "market_verticals", ["slug"])

    # ---------------------------------------------------------------
    # Table 2: listed_companies
    # ---------------------------------------------------------------
    op.create_table(
        "listed_companies",
        sa.Column("id", uuid_type,
                  primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("exchange", sa.String(10), nullable=False),
        sa.Column("isin", sa.String(20), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("listing_type", listing_type_col, nullable=False),
        sa.Column("currency", sa.String(5), default="SGD"),
        sa.Column("vertical_id",
                  uuid_type,
                  sa.ForeignKey("market_verticals.id"), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("employees", sa.Integer, nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("gics_sector", sa.String(100), nullable=True),
        sa.Column("gics_industry", sa.String(100), nullable=True),
        sa.Column("market_cap_sgd", sa.Float, nullable=True),
        sa.Column("pe_ratio", sa.Float, nullable=True),
        sa.Column("ev_ebitda", sa.Float, nullable=True),
        sa.Column("revenue_ttm_sgd", sa.Float, nullable=True),
        sa.Column("gross_margin", sa.Float, nullable=True),
        sa.Column("profit_margin", sa.Float, nullable=True),
        sa.Column("roe", sa.Float, nullable=True),
        sa.Column("dividend_yield", sa.Float, nullable=True),
        sa.Column("nav_per_unit", sa.Float, nullable=True),
        sa.Column("dpu_ttm", sa.Float, nullable=True),
        sa.Column("gearing_ratio", sa.Float, nullable=True),
        sa.Column("is_sg_incorporated", sa.Boolean, default=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
    )
    op.create_index("ix_listed_companies_ticker_exchange", "listed_companies",
                    ["ticker", "exchange"], unique=True)
    op.create_index("ix_listed_companies_vertical", "listed_companies", ["vertical_id"])
    op.create_index("ix_listed_companies_market_cap", "listed_companies", ["market_cap_sgd"])
    op.create_index("ix_listed_companies_isin", "listed_companies", ["isin"])

    # ---------------------------------------------------------------
    # Table 3: company_financial_snapshots
    # ---------------------------------------------------------------
    op.create_table(
        "company_financial_snapshots",
        sa.Column("id", uuid_type,
                  primary_key=True),
        sa.Column("company_id",
                  uuid_type,
                  sa.ForeignKey("listed_companies.id"), nullable=False),
        sa.Column("period_type", period_type_col, nullable=False),
        sa.Column("period_end_date", sa.String(10), nullable=False),
        sa.Column("filing_currency", sa.String(5), default="SGD"),
        sa.Column("fx_to_sgd", sa.Float, default=1.0),
        sa.Column("revenue", sa.Float, nullable=True),
        sa.Column("gross_profit", sa.Float, nullable=True),
        sa.Column("ebitda", sa.Float, nullable=True),
        sa.Column("ebit", sa.Float, nullable=True),
        sa.Column("net_income", sa.Float, nullable=True),
        sa.Column("eps", sa.Float, nullable=True),
        sa.Column("gross_margin", sa.Float, nullable=True),
        sa.Column("ebitda_margin", sa.Float, nullable=True),
        sa.Column("net_margin", sa.Float, nullable=True),
        sa.Column("revenue_growth_yoy", sa.Float, nullable=True),
        sa.Column("net_income_growth_yoy", sa.Float, nullable=True),
        sa.Column("total_assets", sa.Float, nullable=True),
        sa.Column("total_equity", sa.Float, nullable=True),
        sa.Column("total_debt", sa.Float, nullable=True),
        sa.Column("cash_and_equivalents", sa.Float, nullable=True),
        sa.Column("net_debt", sa.Float, nullable=True),
        sa.Column("roe", sa.Float, nullable=True),
        sa.Column("net_debt_ebitda", sa.Float, nullable=True),
        sa.Column("operating_cash_flow", sa.Float, nullable=True),
        sa.Column("capex", sa.Float, nullable=True),
        sa.Column("free_cash_flow", sa.Float, nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
    )
    op.create_index("ix_financial_snapshots_company_period", "company_financial_snapshots",
                    ["company_id", "period_type", "period_end_date"], unique=True)

    # ---------------------------------------------------------------
    # Table 4: vertical_benchmarks
    # ---------------------------------------------------------------
    op.create_table(
        "vertical_benchmarks",
        sa.Column("id", uuid_type,
                  primary_key=True),
        sa.Column("vertical_id",
                  uuid_type,
                  sa.ForeignKey("market_verticals.id"), nullable=False),
        sa.Column("period_type", period_type_col, nullable=False),
        sa.Column("period_label", sa.String(20), nullable=False),
        sa.Column("company_count", sa.Integer, nullable=False),
        sa.Column("revenue_growth_yoy", sa.JSON, default=dict),
        sa.Column("gross_margin", sa.JSON, default=dict),
        sa.Column("ebitda_margin", sa.JSON, default=dict),
        sa.Column("net_margin", sa.JSON, default=dict),
        sa.Column("roe", sa.JSON, default=dict),
        sa.Column("net_debt_ebitda", sa.JSON, default=dict),
        sa.Column("revenue_ttm_sgd", sa.JSON, default=dict),
        sa.Column("leaders", sa.JSON, default=list),
        sa.Column("laggards", sa.JSON, default=list),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
    )
    op.create_index("ix_vertical_benchmarks_vertical_period", "vertical_benchmarks",
                    ["vertical_id", "period_type", "period_label"], unique=True)

    # ---------------------------------------------------------------
    # Table 5: market_articles
    # ---------------------------------------------------------------
    op.create_table(
        "market_articles",
        sa.Column("id", uuid_type,
                  primary_key=True),
        sa.Column("source_name", sa.String(100), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False, unique=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("vertical_slug", sa.String(50), nullable=True),
        sa.Column("signal_type", sa.String(50), nullable=True),
        sa.Column("sentiment", sa.String(20), nullable=True),
        sa.Column("mentioned_tickers", sa.JSON, default=list),
        sa.Column("embedding", sa.Text, nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("is_classified", sa.Boolean, default=False),
    )
    op.create_index("ix_market_articles_published_vertical", "market_articles",
                    ["published_at", "vertical_slug"])
    op.create_index("ix_market_articles_source_published", "market_articles",
                    ["source_name", "published_at"])
    op.create_index("ix_market_articles_source_name", "market_articles", ["source_name"])

    # ---------------------------------------------------------------
    # Table 6: company_documents
    # ---------------------------------------------------------------
    op.create_table(
        "company_documents",
        sa.Column("id", uuid_type,
                  primary_key=True),
        sa.Column("listed_company_id",
                  uuid_type,
                  sa.ForeignKey("listed_companies.id"), nullable=False),
        sa.Column("document_type", doc_type_col, nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_url", sa.String(2000), nullable=False, unique=True),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("published_date", sa.String(10), nullable=True),
        sa.Column("fiscal_year", sa.String(4), nullable=True),
        sa.Column("is_downloaded", sa.Boolean, default=False),
        sa.Column("is_chunked", sa.Boolean, default=False),
        sa.Column("download_error", sa.Text, nullable=True),
        sa.Column("sgx_announcement_id", sa.String(50), nullable=True),
        sa.Column("sgx_category", sa.String(200), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
    )
    op.create_index("ix_company_documents_company_type", "company_documents",
                    ["listed_company_id", "document_type"])
    op.create_index("ix_company_documents_fiscal_year", "company_documents",
                    ["listed_company_id", "fiscal_year"])
    op.create_index("ix_company_documents_sgx_id", "company_documents", ["sgx_announcement_id"])

    # ---------------------------------------------------------------
    # Table 7: document_chunks
    # ---------------------------------------------------------------
    op.create_table(
        "document_chunks",
        sa.Column("id", uuid_type,
                  primary_key=True),
        sa.Column("document_id",
                  uuid_type,
                  sa.ForeignKey("company_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("section_name", sa.String(200), nullable=True),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, default=0),
        sa.Column("embedding", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
    )
    op.create_index("ix_document_chunks_document_index", "document_chunks",
                    ["document_id", "chunk_index"], unique=True)

    # ---------------------------------------------------------------
    # Table 8: company_executives
    # ---------------------------------------------------------------
    op.create_table(
        "company_executives",
        sa.Column("id", uuid_type,
                  primary_key=True),
        sa.Column("listed_company_id",
                  uuid_type,
                  sa.ForeignKey("listed_companies.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("is_ceo", sa.Boolean, default=False),
        sa.Column("is_cfo", sa.Boolean, default=False),
        sa.Column("is_chair", sa.Boolean, default=False),
        sa.Column("since_date", sa.String(10), nullable=True),
        sa.Column("age", sa.Integer, nullable=True),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("last_news_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
    )
    op.create_index("ix_company_executives_company_name", "company_executives",
                    ["listed_company_id", "name"], unique=True)
    op.create_index("ix_company_executives_company_ceo", "company_executives",
                    ["listed_company_id", "is_ceo"])
    op.create_index("ix_company_executives_name", "company_executives", ["name"])


def downgrade() -> None:
    """Drop market intelligence tables in reverse dependency order."""
    op.drop_table("company_executives")
    op.drop_table("document_chunks")
    op.drop_table("company_documents")
    op.drop_table("market_articles")
    op.drop_table("vertical_benchmarks")
    op.drop_table("company_financial_snapshots")
    op.drop_table("listed_companies")
    op.drop_table("market_verticals")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="documenttype").drop(bind, checkfirst=True)
        sa.Enum(name="financialperiodtype").drop(bind, checkfirst=True)
        sa.Enum(name="companylistingtype").drop(bind, checkfirst=True)
