"""Add Phase 7 evaluation datasets, runs, and results.

Revision ID: 0007_phase7
Revises: 0006_phase6
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_phase7"
down_revision: str | None = "0006_phase6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active','archived')",
            name="ck_evaluation_datasets_valid_status",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_evaluation_datasets_workspace_name"),
    )
    op.create_index(
        "ix_evaluation_datasets_workspace_status",
        "evaluation_datasets",
        ["workspace_id", "status"],
    )

    op.create_table(
        "evaluation_dataset_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("case_count > 0", name="ck_evaluation_versions_case_count"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["dataset_id"], ["evaluation_datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dataset_id",
            "version_number",
            name="uq_evaluation_dataset_versions_number",
        ),
        sa.UniqueConstraint("dataset_id", "content_digest", name="uq_evaluation_dataset_digest"),
    )
    op.create_index(
        "ix_evaluation_dataset_versions_workspace",
        "evaluation_dataset_versions",
        ["workspace_id", "dataset_id"],
    )

    op.create_table(
        "evaluation_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("retrieval_mode", sa.String(30), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("relevant_chunk_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "expected_answer_substrings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "expected_citation_quotes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("slices", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("safe_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "retrieval_mode IN ('semantic','lexical','hybrid')",
            name="ck_evaluation_cases_valid_mode",
        ),
        sa.CheckConstraint("top_k BETWEEN 1 AND 20", name="ck_evaluation_cases_top_k"),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["evaluation_dataset_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_version_id", "ordinal", name="uq_evaluation_cases_ordinal"),
    )
    op.create_index(
        "ix_evaluation_cases_workspace_version",
        "evaluation_cases",
        ["workspace_id", "dataset_version_id"],
    )

    op.create_table(
        "evaluation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("run_name", sa.String(160), nullable=False),
        sa.Column("evaluation_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metric_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("code_revision", sa.String(80), nullable=False),
        sa.Column("aggregate_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("slice_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("failure_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("total_cost_usd", sa.Float(), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('succeeded','failed','partial')",
            name="ck_evaluation_runs_valid_status",
        ),
        sa.CheckConstraint("total_cost_usd >= 0", name="ck_evaluation_runs_cost"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["evaluation_dataset_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evaluation_runs_workspace_created",
        "evaluation_runs",
        ["workspace_id", "started_at"],
    )
    op.create_index(
        "ix_evaluation_runs_workspace_dataset",
        "evaluation_runs",
        ["workspace_id", "dataset_version_id"],
    )

    op.create_table(
        "evaluation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("retrieved_chunk_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_cost_usd", sa.Float(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('succeeded','system_failed','metric_failed','missing_labels')",
            name="ck_evaluation_results_valid_status",
        ),
        sa.ForeignKeyConstraint(["answer_run_id"], ["answer_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["evaluation_case_id"], ["evaluation_cases.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evaluation_run_id",
            "evaluation_case_id",
            name="uq_evaluation_result_case",
        ),
    )
    op.create_index(
        "ix_evaluation_results_workspace_run",
        "evaluation_results",
        ["workspace_id", "evaluation_run_id"],
    )

    op.create_table(
        "evaluation_baselines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["dataset_id"], ["evaluation_datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["evaluation_dataset_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "evaluation_run_id", name="uq_evaluation_baseline_run"),
    )
    op.create_index(
        "ix_evaluation_baselines_workspace_dataset",
        "evaluation_baselines",
        ["workspace_id", "dataset_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_baselines_workspace_dataset", table_name="evaluation_baselines")
    op.drop_table("evaluation_baselines")
    op.drop_index("ix_evaluation_results_workspace_run", table_name="evaluation_results")
    op.drop_table("evaluation_results")
    op.drop_index("ix_evaluation_runs_workspace_dataset", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_workspace_created", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    op.drop_index("ix_evaluation_cases_workspace_version", table_name="evaluation_cases")
    op.drop_table("evaluation_cases")
    op.drop_index(
        "ix_evaluation_dataset_versions_workspace", table_name="evaluation_dataset_versions"
    )
    op.drop_table("evaluation_dataset_versions")
    op.drop_index("ix_evaluation_datasets_workspace_status", table_name="evaluation_datasets")
    op.drop_table("evaluation_datasets")
