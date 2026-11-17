"""M14: full-text search helper.

PostgreSQL: to_tsvector/plainto_tsquery, backed by the GIN expression indexes
from migration 0006. Other dialects (SQLite in tests): ILIKE fallback with the
same semantics — every query word must match at least one column (AND).
"""

from sqlalchemy import ColumnElement, func, or_
from sqlalchemy.orm import Session


def is_postgres(db: Session) -> bool:
    return db.bind is not None and db.bind.dialect.name == "postgresql"


def _vector(columns: list[ColumnElement]):
    return func.to_tsvector("simple", func.concat_ws(" ", *[func.coalesce(c, "") for c in columns]))


def fts_condition(db: Session, columns: list[ColumnElement], query: str) -> ColumnElement | None:
    """Match condition for a full-text query, or None for an empty query."""
    words = [w for w in query.split() if w]
    if not words:
        return None
    if is_postgres(db):
        return _vector(columns).op("@@")(func.plainto_tsquery("simple", " ".join(words)))
    cond = None
    for word in words:
        like = f"%{word}%"
        word_cond = or_(*[c.ilike(like) for c in columns])
        cond = word_cond if cond is None else cond & word_cond
    return cond


def fts_rank(db: Session, columns: list[ColumnElement], query: str) -> ColumnElement | None:
    """ts_rank for result ordering on PostgreSQL; None on other dialects."""
    if not is_postgres(db):
        return None
    return func.ts_rank(_vector(columns), func.plainto_tsquery("simple", " ".join(query.split())))
