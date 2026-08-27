"""Add Phase 3 parser provenance and chunk tables.

Revision ID: 0003_phase3
Revises: 0002_phase2
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_phase3"
down_revision: str | None = "0002_phase2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_document_versions_valid_document_version_status",
        "document_versions",
        type_="check",
    )
    op.drop_constraint(
        "ck_ingestion_jobs_valid_ingestion_job_state",
        "ingestion_jobs",
        type_="check",
    )
    op.add_column("document_versions", sa.Column("parser_name", sa.String(80), nullable=True))
    op.add_column("document_versions", sa.Column("parser_version", sa.String(80), nullable=True))
    op.add_column("document_versions", sa.Column("chunker_name", sa.String(80), nullable=True))
    op.add_column("document_versions", sa.Column("chunker_version", sa.String(80), nullable=True))
    op.add_column(
        "document_versions", sa.Column("normalized_object_key", sa.String(1024), nullable=True)
    )
    op.add_column(
        "document_versions", sa.Column("normalized_digest_sha256", sa.String(64), nullable=True)
    )
    op.add_column(
        "document_versions",
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "document_versions",
        sa.Column("character_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "document_versions",
        sa.Column("token_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "document_versions",
        sa.Column(
            "safe_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_document_versions_valid_document_version_status",
        "document_versions",
        "status IN ("
        "'upload_pending','ingestion_pending','verifying','parsing','normalizing',"
        "'chunking','ready','failed','cancelled'"
        ")",
    )
    op.create_check_constraint(
        "ck_document_versions_normalized_sha256",
        "document_versions",
        "normalized_digest_sha256 IS NULL OR normalized_digest_sha256 ~ '^[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        "ck_document_versions_chunk_count",
        "document_versions",
        "chunk_count >= 0 AND character_count >= 0 AND token_count >= 0",
    )
    op.create_check_constraint(
        "ck_ingestion_jobs_valid_ingestion_job_state",
        "ingestion_jobs",
        "state IN ("
        "'pending','claimed','verifying','parsing','normalizing','chunking','publishing',"
        "'succeeded','retry_wait','cancel_requested','cancelled','failed'"
        ")",
    )
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("block_type", sa.String(40), nullable=False),
        sa.Column("heading", sa.String(255), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("start_char", sa.Integer(), nullable=False),
        sa.Column("end_char", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("safe_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.CheckConstraint("ordinal >= 0", name="ck_chunks_valid_chunk_ordinal"),
        sa.CheckConstraint("start_char >= 0", name="ck_chunks_valid_chunk_start"),
        sa.CheckConstraint("end_char >= start_char", name="ck_chunks_valid_chunk_span"),
        sa.CheckConstraint("token_count >= 0", name="ck_chunks_valid_chunk_token_count"),
        sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="ck_chunks_valid_chunk_hash"),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.id"],
            name=op.f("fk_chunks_document_version_id_document_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_chunks_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chunks")),
        sa.UniqueConstraint("document_version_id", "ordinal", name="uq_chunks_version_ordinal"),
    )
    op.create_index(
        "ix_chunks_workspace_version", "chunks", ["workspace_id", "document_version_id"]
    )
    op.create_index("ix_chunks_version_hash", "chunks", ["document_version_id", "content_hash"])


def downgrade() -> None:
    op.drop_index("ix_chunks_version_hash", table_name="chunks")
    op.drop_index("ix_chunks_workspace_version", table_name="chunks")
    op.drop_table("chunks")
    op.drop_constraint(
        "ck_ingestion_jobs_valid_ingestion_job_state",
        "ingestion_jobs",
        type_="check",
    )
    op.drop_constraint(
        "ck_document_versions_chunk_count",
        "document_versions",
        type_="check",
    )
    op.drop_constraint(
        "ck_document_versions_normalized_sha256",
        "document_versions",
        type_="check",
    )
    op.drop_constraint(
        "ck_document_versions_valid_document_version_status",
        "document_versions",
        type_="check",
    )
    op.drop_column("document_versions", "safe_metadata")
    op.drop_column("document_versions", "token_count")
    op.drop_column("document_versions", "character_count")
    op.drop_column("document_versions", "chunk_count")
    op.drop_column("document_versions", "normalized_digest_sha256")
    op.drop_column("document_versions", "normalized_object_key")
    op.drop_column("document_versions", "chunker_version")
    op.drop_column("document_versions", "chunker_name")
    op.drop_column("document_versions", "parser_version")
    op.drop_column("document_versions", "parser_name")
    op.create_check_constraint(
        "ck_ingestion_jobs_valid_ingestion_job_state",
        "ingestion_jobs",
        "state IN ("
        "'pending','claimed','verifying','publishing','succeeded','retry_wait',"
        "'cancel_requested','cancelled','failed'"
        ")",
    )
    op.create_check_constraint(
        "ck_document_versions_valid_document_version_status",
        "document_versions",
        "status IN ('upload_pending','ingestion_pending','verifying','ready','failed','cancelled')",
    )
