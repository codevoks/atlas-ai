"""Add Phase 4 embedding sets, chunk embeddings, and semantic states.

Revision ID: 0004_phase4
Revises: 0003_phase3
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_phase4"
down_revision: str | None = "0003_phase3"
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
    op.create_table(
        "embedding_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("normalized", sa.Boolean(), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
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
        sa.CheckConstraint("dimension >= 8", name="ck_embedding_sets_valid_embedding_dimension"),
        sa.CheckConstraint(
            "status IN ('active','deprecated')", name="ck_embedding_sets_valid_status"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_embedding_sets_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_embedding_sets")),
        sa.UniqueConstraint(
            "workspace_id",
            "provider",
            "model",
            "model_version",
            "dimension",
            "normalized",
            name="uq_embedding_sets_space",
        ),
    )
    op.create_index(
        "ix_embedding_sets_workspace_status", "embedding_sets", ["workspace_id", "status"]
    )
    op.add_column(
        "document_versions",
        sa.Column("embedding_set_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "document_versions",
        sa.Column("embedding_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_foreign_key(
        op.f("fk_document_versions_embedding_set_id_embedding_sets"),
        "document_versions",
        "embedding_sets",
        ["embedding_set_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_document_versions_embedding_count",
        "document_versions",
        "embedding_count >= 0",
    )
    op.create_table(
        "chunk_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding_set_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vector", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="ready"),
        sa.Column("token_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
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
        sa.CheckConstraint("token_count >= 0", name="ck_chunk_embeddings_valid_token_count"),
        sa.CheckConstraint("status IN ('ready','failed')", name="ck_chunk_embeddings_valid_status"),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["chunks.id"],
            name=op.f("fk_chunk_embeddings_chunk_id_chunks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.id"],
            name=op.f("fk_chunk_embeddings_document_version_id_document_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_set_id"],
            ["embedding_sets.id"],
            name=op.f("fk_chunk_embeddings_embedding_set_id_embedding_sets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_chunk_embeddings_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chunk_embeddings")),
        sa.UniqueConstraint("chunk_id", "embedding_set_id", name="uq_chunk_embeddings_chunk_set"),
    )
    op.create_index(
        "ix_chunk_embeddings_workspace_set",
        "chunk_embeddings",
        ["workspace_id", "embedding_set_id"],
    )
    op.create_index(
        "ix_chunk_embeddings_version_set",
        "chunk_embeddings",
        ["document_version_id", "embedding_set_id"],
    )
    op.create_check_constraint(
        "ck_document_versions_valid_document_version_status",
        "document_versions",
        "status IN ("
        "'upload_pending','ingestion_pending','verifying','parsing','normalizing',"
        "'chunking','embedding','ready','failed','cancelled'"
        ")",
    )
    op.create_check_constraint(
        "ck_ingestion_jobs_valid_ingestion_job_state",
        "ingestion_jobs",
        "state IN ("
        "'pending','claimed','verifying','parsing','normalizing','chunking','embedding',"
        "'publishing','succeeded','retry_wait','cancel_requested','cancelled','failed'"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ingestion_jobs_valid_ingestion_job_state",
        "ingestion_jobs",
        type_="check",
    )
    op.drop_constraint(
        "ck_document_versions_valid_document_version_status",
        "document_versions",
        type_="check",
    )
    op.drop_index("ix_chunk_embeddings_version_set", table_name="chunk_embeddings")
    op.drop_index("ix_chunk_embeddings_workspace_set", table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")
    op.drop_constraint(
        "ck_document_versions_embedding_count",
        "document_versions",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_document_versions_embedding_set_id_embedding_sets"),
        "document_versions",
        type_="foreignkey",
    )
    op.drop_column("document_versions", "embedding_count")
    op.drop_column("document_versions", "embedding_set_id")
    op.drop_index("ix_embedding_sets_workspace_status", table_name="embedding_sets")
    op.drop_table("embedding_sets")
    op.create_check_constraint(
        "ck_ingestion_jobs_valid_ingestion_job_state",
        "ingestion_jobs",
        "state IN ("
        "'pending','claimed','verifying','parsing','normalizing','chunking','publishing',"
        "'succeeded','retry_wait','cancel_requested','cancelled','failed'"
        ")",
    )
    op.create_check_constraint(
        "ck_document_versions_valid_document_version_status",
        "document_versions",
        "status IN ("
        "'upload_pending','ingestion_pending','verifying','parsing','normalizing',"
        "'chunking','ready','failed','cancelled'"
        ")",
    )
