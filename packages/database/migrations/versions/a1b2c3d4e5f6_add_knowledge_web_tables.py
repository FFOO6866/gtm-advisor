"""Add Knowledge Web tables

Revision ID: a1b2c3d4e5f6
Revises: 54b79669bb7d
Create Date: 2026-01-29 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "54b79669bb7d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add Knowledge Web tables for evidence-backed intelligence graph."""
    # Create enums for Knowledge Web
    sourcetype_enum = sa.Enum(
        "ACRA",
        "EODHD",
        "NEWSAPI",
        "PERPLEXITY",
        "WEB_SCRAPE",
        "LINKEDIN",
        "JOB_BOARD",
        "GOVERNMENT",
        "REVIEW_SITE",
        "PRESS_RELEASE",
        "SEC_FILING",
        "USER_INPUT",
        name="sourcetype",
    )
    facttype_enum = sa.Enum(
        "COMPANY_INFO",
        "FUNDING",
        "EXECUTIVE",
        "PRODUCT",
        "PARTNERSHIP",
        "EXPANSION",
        "HIRING",
        "TECHNOLOGY",
        "FINANCIAL",
        "MARKET_TREND",
        "COMPETITOR_MOVE",
        "REGULATION",
        "ACQUISITION",
        "SENTIMENT",
        name="facttype",
    )
    entitytype_enum = sa.Enum(
        "COMPANY",
        "PERSON",
        "PRODUCT",
        "INVESTOR",
        "INDUSTRY",
        "TECHNOLOGY",
        "LOCATION",
        name="entitytype",
    )
    relationtype_enum = sa.Enum(
        "WORKS_AT",
        "FOUNDED",
        "INVESTED_IN",
        "COMPETES_WITH",
        "PARTNERS_WITH",
        "ACQUIRED",
        "USES_TECHNOLOGY",
        "OPERATES_IN",
        "SUPPLIES_TO",
        "FORMER_EMPLOYEE",
        name="relationtype",
    )

    # Create evidenced_facts table
    op.create_table(
        "evidenced_facts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("fact_type", facttype_enum, nullable=False),  # Index in __table_args__
        sa.Column("source_type", sourcetype_enum, nullable=False),  # Index in __table_args__
        sa.Column("source_name", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("raw_excerpt", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=True),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("verification_count", sa.Integer(), nullable=True),
        sa.Column("extracted_data", sa.JSON(), nullable=True),
        sa.Column("mcp_server", sa.String(length=50), nullable=True),
        sa.Column("processing_model", sa.String(length=50), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=True),
        sa.Column("is_stale", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidenced_facts_fact_type", "evidenced_facts", ["fact_type"], unique=False)
    op.create_index(
        "ix_evidenced_facts_source_type", "evidenced_facts", ["source_type"], unique=False
    )
    op.create_index(
        "ix_evidenced_facts_captured_at", "evidenced_facts", ["captured_at"], unique=False
    )
    op.create_index("ix_evidenced_facts_confidence", "evidenced_facts", ["confidence"], unique=False)
    op.create_index(
        "ix_evidenced_facts_source_type_captured",
        "evidenced_facts",
        ["source_type", "captured_at"],
        unique=False,
    )

    # Create entities table
    op.create_table(
        "entities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("entity_type", entitytype_enum, nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("canonical_name", sa.String(length=300), nullable=True),
        sa.Column("acra_uen", sa.String(length=20), nullable=True),
        sa.Column("linkedin_url", sa.String(length=500), nullable=True),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("external_ids", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.Column("fact_count", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("merged_into_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("acra_uen"),
    )
    op.create_index("ix_entities_entity_type", "entities", ["entity_type"], unique=False)
    op.create_index("ix_entities_name", "entities", ["name"], unique=False)
    op.create_index("ix_entities_canonical_name", "entities", ["canonical_name"], unique=False)
    op.create_index("ix_entities_acra_uen", "entities", ["acra_uen"], unique=False)
    op.create_index("ix_entities_type_name", "entities", ["entity_type", "name"], unique=False)

    # Create entity_relations table
    op.create_table(
        "entity_relations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_entity_id", sa.UUID(), nullable=False),
        sa.Column("target_entity_id", sa.UUID(), nullable=False),
        sa.Column("relation_type", relationtype_enum, nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("valid_from", sa.DateTime(), nullable=True),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["source_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["target_entity_id"], ["entities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_entity_relations_source", "entity_relations", ["source_entity_id"], unique=False
    )
    op.create_index(
        "ix_entity_relations_target", "entity_relations", ["target_entity_id"], unique=False
    )
    op.create_index("ix_entity_relations_type", "entity_relations", ["relation_type"], unique=False)
    op.create_index(
        "ix_entity_relations_source_target",
        "entity_relations",
        ["source_entity_id", "target_entity_id", "relation_type"],
        unique=False,
    )

    # Create fact_entity_links table
    op.create_table(
        "fact_entity_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("fact_id", sa.UUID(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=True),
        sa.Column("relevance", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["fact_id"], ["evidenced_facts.id"]),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fact_entity_links_fact", "fact_entity_links", ["fact_id"], unique=False)
    op.create_index("ix_fact_entity_links_entity", "fact_entity_links", ["entity_id"], unique=False)
    op.create_index(
        "ix_fact_entity_links_fact_entity",
        "fact_entity_links",
        ["fact_id", "entity_id"],
        unique=True,
    )

    # Create fact_relation_links table
    op.create_table(
        "fact_relation_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("fact_id", sa.UUID(), nullable=False),
        sa.Column("relation_id", sa.UUID(), nullable=False),
        sa.Column("is_primary_evidence", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["fact_id"], ["evidenced_facts.id"]),
        sa.ForeignKeyConstraint(["relation_id"], ["entity_relations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fact_relation_links_fact", "fact_relation_links", ["fact_id"], unique=False)
    op.create_index(
        "ix_fact_relation_links_relation", "fact_relation_links", ["relation_id"], unique=False
    )
    op.create_index(
        "ix_fact_relation_links_fact_relation",
        "fact_relation_links",
        ["fact_id", "relation_id"],
        unique=True,
    )

    # Create lead_justifications table
    op.create_table(
        "lead_justifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("signal_category", sa.String(length=50), nullable=False),
        sa.Column("signal_type", sa.String(length=100), nullable=False),
        sa.Column("signal_description", sa.Text(), nullable=False),
        sa.Column("impact_score", sa.Float(), nullable=True),
        sa.Column("evidence_fact_ids", sa.JSON(), nullable=True),
        sa.Column("evidence_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_justifications_lead", "lead_justifications", ["lead_id"], unique=False)
    op.create_index(
        "ix_lead_justifications_category",
        "lead_justifications",
        ["signal_category"],
        unique=False,
    )
    op.create_index(
        "ix_lead_justifications_type", "lead_justifications", ["signal_type"], unique=False
    )

    # Create competitor_signals table
    op.create_table(
        "competitor_signals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("competitor_id", sa.UUID(), nullable=False),
        sa.Column("signal_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("primary_fact_id", sa.UUID(), nullable=True),
        sa.Column("supporting_fact_ids", sa.JSON(), nullable=True),
        sa.Column("our_response_options", sa.JSON(), nullable=True),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("is_acknowledged", sa.Boolean(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("response_status", sa.String(length=20), nullable=True),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["competitor_id"], ["competitors.id"]),
        sa.ForeignKeyConstraint(["primary_fact_id"], ["evidenced_facts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_competitor_signals_competitor", "competitor_signals", ["competitor_id"], unique=False
    )
    op.create_index(
        "ix_competitor_signals_type", "competitor_signals", ["signal_type"], unique=False
    )
    op.create_index(
        "ix_competitor_signals_severity", "competitor_signals", ["severity"], unique=False
    )
    op.create_index(
        "ix_competitor_signals_detected", "competitor_signals", ["detected_at"], unique=False
    )

    # Create mcp_data_sources table
    op.create_table(
        "mcp_data_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("source_type", sourcetype_enum, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("endpoint_url", sa.String(length=500), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=True),
        sa.Column("is_healthy", sa.Boolean(), nullable=True),
        sa.Column("last_health_check", sa.DateTime(), nullable=True),
        sa.Column("last_sync", sa.DateTime(), nullable=True),
        sa.Column("total_facts_produced", sa.Integer(), nullable=True),
        sa.Column("facts_today", sa.Integer(), nullable=True),
        sa.Column("avg_confidence", sa.Float(), nullable=True),
        sa.Column("rate_limit_per_hour", sa.Integer(), nullable=True),
        sa.Column("requests_this_hour", sa.Integer(), nullable=True),
        sa.Column("rate_limit_reset_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_mcp_data_sources_name", "mcp_data_sources", ["name"], unique=False)
    op.create_index("ix_mcp_data_sources_type", "mcp_data_sources", ["source_type"], unique=False)
    op.create_index("ix_mcp_data_sources_enabled", "mcp_data_sources", ["is_enabled"], unique=False)


def downgrade() -> None:
    """Remove Knowledge Web tables."""
    # Drop tables in reverse order of creation (respecting foreign keys)
    op.drop_index("ix_mcp_data_sources_enabled", table_name="mcp_data_sources")
    op.drop_index("ix_mcp_data_sources_type", table_name="mcp_data_sources")
    op.drop_index("ix_mcp_data_sources_name", table_name="mcp_data_sources")
    op.drop_table("mcp_data_sources")

    op.drop_index("ix_competitor_signals_detected", table_name="competitor_signals")
    op.drop_index("ix_competitor_signals_severity", table_name="competitor_signals")
    op.drop_index("ix_competitor_signals_type", table_name="competitor_signals")
    op.drop_index("ix_competitor_signals_competitor", table_name="competitor_signals")
    op.drop_table("competitor_signals")

    op.drop_index("ix_lead_justifications_type", table_name="lead_justifications")
    op.drop_index("ix_lead_justifications_category", table_name="lead_justifications")
    op.drop_index("ix_lead_justifications_lead", table_name="lead_justifications")
    op.drop_table("lead_justifications")

    op.drop_index("ix_fact_relation_links_fact_relation", table_name="fact_relation_links")
    op.drop_index("ix_fact_relation_links_relation", table_name="fact_relation_links")
    op.drop_index("ix_fact_relation_links_fact", table_name="fact_relation_links")
    op.drop_table("fact_relation_links")

    op.drop_index("ix_fact_entity_links_fact_entity", table_name="fact_entity_links")
    op.drop_index("ix_fact_entity_links_entity", table_name="fact_entity_links")
    op.drop_index("ix_fact_entity_links_fact", table_name="fact_entity_links")
    op.drop_table("fact_entity_links")

    op.drop_index("ix_entity_relations_source_target", table_name="entity_relations")
    op.drop_index("ix_entity_relations_type", table_name="entity_relations")
    op.drop_index("ix_entity_relations_target", table_name="entity_relations")
    op.drop_index("ix_entity_relations_source", table_name="entity_relations")
    op.drop_table("entity_relations")

    op.drop_index("ix_entities_type_name", table_name="entities")
    op.drop_index("ix_entities_acra_uen", table_name="entities")
    op.drop_index("ix_entities_canonical_name", table_name="entities")
    op.drop_index("ix_entities_name", table_name="entities")
    op.drop_index("ix_entities_entity_type", table_name="entities")
    op.drop_table("entities")

    op.drop_index("ix_evidenced_facts_source_type_captured", table_name="evidenced_facts")
    op.drop_index("ix_evidenced_facts_confidence", table_name="evidenced_facts")
    op.drop_index("ix_evidenced_facts_captured_at", table_name="evidenced_facts")
    op.drop_index("ix_evidenced_facts_source_type", table_name="evidenced_facts")
    op.drop_index("ix_evidenced_facts_fact_type", table_name="evidenced_facts")
    op.drop_table("evidenced_facts")

    # Drop enums
    sa.Enum(name="relationtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="entitytype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="facttype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="sourcetype").drop(op.get_bind(), checkfirst=True)
