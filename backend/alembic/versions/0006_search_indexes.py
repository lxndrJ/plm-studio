"""M14: full-text search indexes (PostgreSQL GIN expression indexes)

Search runs over parts (part_number, name, description) and documents
(doc_number, title) via to_tsvector at query time (app/services/search.py).
SQLite (tests/dev) has no tsvector, so the indexes are PostgreSQL-only; the
search falls back to ILIKE there.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARTS_FTS = (
    "CREATE INDEX IF NOT EXISTS idx_parts_search_fts ON parts USING gin ("
    "to_tsvector('simple', coalesce(part_number, '') || ' ' || coalesce(name, '') || ' ' "
    "|| coalesce(description, '')))"
)
DOCUMENTS_FTS = (
    "CREATE INDEX IF NOT EXISTS idx_documents_search_fts ON documents USING gin ("
    "to_tsvector('simple', coalesce(doc_number, '') || ' ' || coalesce(title, '')))"
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(PARTS_FTS)
    op.execute(DOCUMENTS_FTS)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS idx_documents_search_fts")
    op.execute("DROP INDEX IF EXISTS idx_parts_search_fts")
