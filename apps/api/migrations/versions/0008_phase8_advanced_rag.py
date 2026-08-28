"""Add Phase 8 retrieval provenance fields.

Revision ID: 0008_phase8
Revises: 0007_phase7
Create Date: 2026-08-28 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_phase8"
down_revision: str | None = "0007_phase7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "answer_evidence",
        sa.Column(
            "retrieval_provenance",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "evaluation_cases",
        sa.Column(
            "retrieval_config_version",
            sa.String(length=100),
            nullable=False,
            server_default="phase5-postgres-fts-rrf-v1",
        ),
    )
    op.alter_column("answer_evidence", "retrieval_provenance", server_default=None)
    op.alter_column("evaluation_cases", "retrieval_config_version", server_default=None)


def downgrade() -> None:
    op.drop_column("evaluation_cases", "retrieval_config_version")
    op.drop_column("answer_evidence", "retrieval_provenance")
