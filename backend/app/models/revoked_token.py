import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class RevokedToken(Base):
    """Denylist for logged-out tokens (jti). Rows are pure bookkeeping: they
    expire with the token itself and are purged opportunistically."""

    __tablename__ = "revoked_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    jti: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    token_type: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
