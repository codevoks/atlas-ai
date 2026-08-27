"""Add Phase 6 answer runs, evidence, and citations.

Revision ID: 0006_phase6
Revises: 0005_phase5
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_phase6"
down_revision: str | None = "0005_phase5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "answer_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("retrieval_mode", sa.String(30), nullable=False),
        sa.Column("retrieval_config_version", sa.String(120), nullable=False),
        sa.Column("generation_provider", sa.String(80), nullable=False),
        sa.Column("generation_model", sa.String(160), nullable=False),
        sa.Column("generation_model_version", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(120), nullable=False),
        sa.Column("grounding_status", sa.String(50), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("context_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_cost_usd", sa.Float(), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
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
            "status IN ('succeeded','failed','refused')",
            name="ck_answer_runs_valid_status",
        ),
        sa.CheckConstraint("input_tokens >= 0", name="ck_answer_runs_valid_input_tokens"),
        sa.CheckConstraint("output_tokens >= 0", name="ck_answer_runs_valid_output_tokens"),
        sa.CheckConstraint("total_cost_usd >= 0", name="ck_answer_runs_valid_cost"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_answer_runs_workspace_created", "answer_runs", ["workspace_id", "created_at"]
    )
    op.create_index("ix_answer_runs_workspace_status", "answer_runs", ["workspace_id", "status"])

    op.create_table(
        "answer_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("document_title", sa.String(255), nullable=False),
        sa.Column("retrieval_stage", sa.String(30), nullable=False),
        sa.Column("retrieval_score", sa.Float(), nullable=False),
        sa.Column("semantic_score", sa.Float(), nullable=True),
        sa.Column("lexical_score", sa.Float(), nullable=True),
        sa.Column("rrf_score", sa.Float(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("start_char", sa.Integer(), nullable=False),
        sa.Column("end_char", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["answer_run_id"], ["answer_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["document_version_id"], ["document_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("answer_run_id", "rank", name="uq_answer_evidence_run_rank"),
    )
    op.create_index(
        "ix_answer_evidence_workspace_run",
        "answer_evidence",
        ["workspace_id", "answer_run_id"],
    )

    op.create_table(
        "citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("marker", sa.String(20), nullable=False),
        sa.Column("answer_start_char", sa.Integer(), nullable=False),
        sa.Column("answer_end_char", sa.Integer(), nullable=False),
        sa.Column("evidence_start_char", sa.Integer(), nullable=False),
        sa.Column("evidence_end_char", sa.Integer(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('verified','rejected')", name="ck_citations_valid_status"),
        sa.ForeignKeyConstraint(["answer_evidence_id"], ["answer_evidence.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["answer_run_id"], ["answer_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_citations_workspace_run", "citations", ["workspace_id", "answer_run_id"])


def downgrade() -> None:
    op.drop_index("ix_citations_workspace_run", table_name="citations")
    op.drop_table("citations")
    op.drop_index("ix_answer_evidence_workspace_run", table_name="answer_evidence")
    op.drop_table("answer_evidence")
    op.drop_index("ix_answer_runs_workspace_status", table_name="answer_runs")
    op.drop_index("ix_answer_runs_workspace_created", table_name="answer_runs")
    op.drop_table("answer_runs")
