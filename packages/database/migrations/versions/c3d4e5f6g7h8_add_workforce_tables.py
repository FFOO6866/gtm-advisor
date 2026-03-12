"""Add workforce tables: signals, sequences, approvals, attribution, playbooks

Revision ID: c3d4e5f6g7h8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-10 09:00:00.000000

Creates 7 tables required by the Digital Workforce feature:
  signal_events         — market signals detected by SignalMonitorAgent
  sequence_templates    — reusable multi-step outreach templates
  sequence_steps        — individual steps within a template
  sequence_enrollments  — leads enrolled in sequences
  approval_queue        — human approval gate for all outreach emails
  attribution_events    — ROI tracking (email_sent → reply → deal)
  playbook_templates    — built-in GTM playbook configurations

Also creates 4 enums: signaltype, signalurgency, enrollmentstatus, approvalstatus
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6g7h8"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create workforce feature tables and enums."""

    # --- Enums ---
    signaltype_enum = sa.Enum(
        "funding", "acquisition", "product_launch", "regulation", "expansion",
        "hiring", "layoff", "partnership", "market_trend", "competitor_news", "general_news",
        name="signaltype",
    )
    signalurgency_enum = sa.Enum(
        "immediate", "this_week", "this_month", "monitor",
        name="signalurgency",
    )
    enrollmentstatus_enum = sa.Enum(
        "active", "paused", "completed", "rejected", "opted_out",
        name="enrollmentstatus",
    )
    approvalstatus_enum = sa.Enum(
        "pending", "approved", "rejected", "edited_approved",
        name="approvalstatus",
    )

    # --- signal_events ---
    op.create_table(
        "signal_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("signal_type", signaltype_enum, nullable=False),
        sa.Column("urgency", signalurgency_enum, nullable=False),
        sa.Column("headline", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("competitors_mentioned", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("is_actioned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("actioned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signal_events_company_id", "signal_events", ["company_id"])
    op.create_index("ix_signal_events_signal_type", "signal_events", ["signal_type"])
    op.create_index("ix_signal_events_urgency", "signal_events", ["urgency"])
    op.create_index("ix_signal_events_created_at", "signal_events", ["created_at"])

    # --- sequence_templates ---
    op.create_table(
        "sequence_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("playbook_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("total_steps", sa.Integer(), nullable=True),
        sa.Column("total_duration_days", sa.Integer(), nullable=True),
        sa.Column("is_system_template", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sequence_templates_company_id", "sequence_templates", ["company_id"])
    op.create_index("ix_sequence_templates_playbook_type", "sequence_templates", ["playbook_type"])

    # --- sequence_steps ---
    op.create_table(
        "sequence_steps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("template_id", sa.UUID(), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("day_offset", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=50), nullable=False),
        sa.Column("subject_pattern", sa.String(length=300), nullable=False),
        sa.Column("body_instructions", sa.Text(), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=True),
        sa.Column("requires_approval", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["template_id"], ["sequence_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sequence_steps_template_id", "sequence_steps", ["template_id"])
    op.create_index("ix_sequence_steps_step_number", "sequence_steps", ["step_number"])

    # --- sequence_enrollments ---
    op.create_table(
        "sequence_enrollments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("template_id", sa.UUID(), nullable=False),
        sa.Column("status", enrollmentstatus_enum, nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("next_step_due", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pause_reason", sa.String(length=200), nullable=True),
        sa.Column("emails_sent", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger_signal_id", sa.UUID(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["sequence_templates.id"]),
        sa.ForeignKeyConstraint(["trigger_signal_id"], ["signal_events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sequence_enrollments_company_id", "sequence_enrollments", ["company_id"])
    op.create_index("ix_sequence_enrollments_lead_id", "sequence_enrollments", ["lead_id"])
    op.create_index("ix_sequence_enrollments_status", "sequence_enrollments", ["status"])
    op.create_index("ix_sequence_enrollments_next_step_due", "sequence_enrollments", ["next_step_due"])

    # --- approval_queue ---
    op.create_table(
        "approval_queue",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("enrollment_id", sa.UUID(), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("status", approvalstatus_enum, nullable=False),
        sa.Column("proposed_subject", sa.String(length=500), nullable=False),
        sa.Column("proposed_body", sa.Text(), nullable=False),
        sa.Column("final_subject", sa.String(length=500), nullable=True),
        sa.Column("final_body", sa.Text(), nullable=True),
        sa.Column("to_email", sa.String(length=300), nullable=False),
        sa.Column("to_name", sa.String(length=200), nullable=True),
        sa.Column("sequence_name", sa.String(length=200), nullable=True),
        sa.Column("approved_by", sa.String(length=200), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_send_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_id", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enrollment_id"], ["sequence_enrollments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_queue_company_id", "approval_queue", ["company_id"])
    op.create_index("ix_approval_queue_status", "approval_queue", ["status"])
    op.create_index("ix_approval_queue_lead_id", "approval_queue", ["lead_id"])
    op.create_index("ix_approval_queue_created_at", "approval_queue", ["created_at"])

    # --- attribution_events ---
    op.create_table(
        "attribution_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("approval_item_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("pipeline_value_sgd", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("recorded_by", sa.String(length=50), nullable=False, server_default=sa.text("'system'")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["approval_item_id"], ["approval_queue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attribution_events_company_id", "attribution_events", ["company_id"])
    op.create_index("ix_attribution_events_lead_id", "attribution_events", ["lead_id"])
    op.create_index("ix_attribution_events_event_type", "attribution_events", ["event_type"])
    op.create_index("ix_attribution_events_occurred_at", "attribution_events", ["occurred_at"])

    # --- playbook_templates ---
    op.create_table(
        "playbook_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("playbook_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("best_for", sa.Text(), nullable=False),
        sa.Column("steps_count", sa.Integer(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("success_rate_benchmark", sa.String(length=200), nullable=True),
        sa.Column("sequence_config", sa.JSON(), nullable=True),
        sa.Column("scoring_weights", sa.JSON(), nullable=True),
        sa.Column("is_singapore_specific", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("playbook_type"),
    )
    op.create_index("ix_playbook_templates_playbook_type", "playbook_templates", ["playbook_type"])
    op.create_index("ix_playbook_templates_is_active", "playbook_templates", ["is_active"])


def downgrade() -> None:
    """Drop workforce feature tables and enums (reverse order to respect FKs)."""
    op.drop_index("ix_playbook_templates_is_active", table_name="playbook_templates")
    op.drop_index("ix_playbook_templates_playbook_type", table_name="playbook_templates")
    op.drop_table("playbook_templates")

    op.drop_index("ix_attribution_events_occurred_at", table_name="attribution_events")
    op.drop_index("ix_attribution_events_event_type", table_name="attribution_events")
    op.drop_index("ix_attribution_events_lead_id", table_name="attribution_events")
    op.drop_index("ix_attribution_events_company_id", table_name="attribution_events")
    op.drop_table("attribution_events")

    op.drop_index("ix_approval_queue_created_at", table_name="approval_queue")
    op.drop_index("ix_approval_queue_lead_id", table_name="approval_queue")
    op.drop_index("ix_approval_queue_status", table_name="approval_queue")
    op.drop_index("ix_approval_queue_company_id", table_name="approval_queue")
    op.drop_table("approval_queue")

    op.drop_index("ix_sequence_enrollments_next_step_due", table_name="sequence_enrollments")
    op.drop_index("ix_sequence_enrollments_status", table_name="sequence_enrollments")
    op.drop_index("ix_sequence_enrollments_lead_id", table_name="sequence_enrollments")
    op.drop_index("ix_sequence_enrollments_company_id", table_name="sequence_enrollments")
    op.drop_table("sequence_enrollments")

    op.drop_index("ix_sequence_steps_step_number", table_name="sequence_steps")
    op.drop_index("ix_sequence_steps_template_id", table_name="sequence_steps")
    op.drop_table("sequence_steps")

    op.drop_index("ix_sequence_templates_playbook_type", table_name="sequence_templates")
    op.drop_index("ix_sequence_templates_company_id", table_name="sequence_templates")
    op.drop_table("sequence_templates")

    op.drop_index("ix_signal_events_created_at", table_name="signal_events")
    op.drop_index("ix_signal_events_urgency", table_name="signal_events")
    op.drop_index("ix_signal_events_signal_type", table_name="signal_events")
    op.drop_index("ix_signal_events_company_id", table_name="signal_events")
    op.drop_table("signal_events")

    # Drop enums
    sa.Enum(name="approvalstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="enrollmentstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="signalurgency").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="signaltype").drop(op.get_bind(), checkfirst=True)
