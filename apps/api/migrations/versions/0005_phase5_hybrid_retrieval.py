"""Add Phase 5 lexical retrieval index.

Revision ID: 0005_phase5
Revises: 0004_phase4
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_phase5"
down_revision: str | None = "0004_phase4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_chunks_fts_english",
        "chunks",
        [sa.text("to_tsvector('english'::regconfig, text)")],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_chunks_fts_english", table_name="chunks")
