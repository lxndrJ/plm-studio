"""add preview_jobs queue table (M4)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _uuid():
    return UUID if _is_pg() else sa.types.Uuid()


def _pk_uuid():
    return {"server_default": sa.text("gen_random_uuid()")} if _is_pg() else {}


def upgrade() -> None:
    op.create_table(
        "preview_jobs",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("doc_file_id", _uuid(), sa.ForeignKey("doc_files.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("derivative_file_id", _uuid(), sa.ForeignKey("doc_files.id"), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_preview_jobs_doc_file_id", "preview_jobs", ["doc_file_id"])
    op.create_index("ix_preview_jobs_status", "preview_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_preview_jobs_status", table_name="preview_jobs")
    op.drop_index("ix_preview_jobs_doc_file_id", table_name="preview_jobs")
    op.drop_table("preview_jobs")
