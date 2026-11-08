import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, now_ts, uuid_pk


class PreviewJob(Base):
    """Queue row for derivative generation (previews/ worker polls this table)."""

    __tablename__ = "preview_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    doc_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("doc_files.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued", index=True)
    derivative_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("doc_files.id"), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = now_ts()
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
