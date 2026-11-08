import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, now_ts, uuid_pk
from app.models.numbering import JsonB

CONFIRMATION_STATUSES = ("proposed", "approved", "rejected", "executed", "expired")


class Confirmation(Base):
    """Confirmation token for proposed writes (agent path). The write is only
    committed after a user approves it via POST /confirmations/{id}/approve."""

    __tablename__ = "confirmations"

    id: Mapped[uuid.UUID] = uuid_pk()
    action: Mapped[str] = mapped_column(String, nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JsonB, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="proposed", index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = now_ts()
    expires_at: Mapped[datetime] = now_ts()
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
