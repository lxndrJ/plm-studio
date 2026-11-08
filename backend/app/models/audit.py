import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, now_ts
from app.models.numbering import JsonB


class AuditLog(Base):
    """Append-only. No UPDATE/DELETE grants are ever given out for this table;
    the API exposes no mutating endpoints for it."""

    __tablename__ = "audit_log"

    # bigserial on Postgres; plain INTEGER (rowid alias) on SQLite so autoincrement works there too
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    entity_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    old_values: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    at: Mapped[datetime] = now_ts()

    user = relationship("User", back_populates="audit_entries")
