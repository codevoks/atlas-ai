"""Add Phase 10 security guardrail tables.

Revision ID: 0010_phase10
Revises: 0009_phase9
Create Date: 2026-08-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_phase10"
down_revision: str | None = "0009_phase9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "security_policy_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("config_version", sa.String(length=120), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version >= 1", name="valid_security_policy_config_version"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "policy_name",
            "version",
            name="uq_security_policy_configs_workspace_policy_version",
        ),
    )
    op.create_index(
        "ix_security_policy_configs_workspace_active",
        "security_policy_configs",
        ["workspace_id", "policy_name", "active"],
    )

    op.create_table(
        "security_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("control_version", sa.String(length=120), nullable=False),
        sa.Column("safe_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "severity IN ('info','low','medium','high','critical')",
            name="valid_security_event_severity",
        ),
        sa.CheckConstraint(
            "outcome IN ('allowed','blocked','detected')",
            name="valid_security_event_outcome",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_security_events_workspace_created",
        "security_events",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_security_events_workspace_outcome",
        "security_events",
        ["workspace_id", "outcome"],
    )
    op.create_index(
        "ix_security_events_workspace_type",
        "security_events",
        ["workspace_id", "event_type"],
    )

    op.create_table(
        "quota_counters",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(length=120), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("quota_limit", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("count >= 0", name="valid_quota_count"),
        sa.CheckConstraint("quota_limit >= 1", name="valid_quota_limit"),
        sa.CheckConstraint("window_seconds >= 1", name="valid_quota_window_seconds"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "actor_user_id",
            "operation",
            "window_start",
            name="uq_quota_counters_scope_window",
        ),
    )
    op.create_index(
        "ix_quota_counters_workspace_operation",
        "quota_counters",
        ["workspace_id", "operation"],
    )

    op.create_table(
        "content_trust_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trust_status", sa.String(length=30), nullable=False),
        sa.Column("classifier_version", sa.String(length=120), nullable=False),
        sa.Column("signals", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.String(length=240), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "trust_status IN ('trusted','untrusted','quarantined')",
            name="valid_content_trust_status",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "resource_type",
            "resource_id",
            name="uq_content_trust_resource",
        ),
    )
    op.create_index(
        "ix_content_trust_workspace_status",
        "content_trust_records",
        ["workspace_id", "trust_status"],
    )

    op.create_table(
        "retention_tombstones",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deleted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.String(length=160), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("safe_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["deleted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "resource_type",
            "resource_id",
            name="uq_retention_tombstones_resource",
        ),
    )
    op.create_index(
        "ix_retention_tombstones_workspace_created",
        "retention_tombstones",
        ["workspace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_retention_tombstones_workspace_created", table_name="retention_tombstones")
    op.drop_table("retention_tombstones")
    op.drop_index("ix_content_trust_workspace_status", table_name="content_trust_records")
    op.drop_table("content_trust_records")
    op.drop_index("ix_quota_counters_workspace_operation", table_name="quota_counters")
    op.drop_table("quota_counters")
    op.drop_index("ix_security_events_workspace_type", table_name="security_events")
    op.drop_index("ix_security_events_workspace_outcome", table_name="security_events")
    op.drop_index("ix_security_events_workspace_created", table_name="security_events")
    op.drop_table("security_events")
    op.drop_index(
        "ix_security_policy_configs_workspace_active", table_name="security_policy_configs"
    )
    op.drop_table("security_policy_configs")
