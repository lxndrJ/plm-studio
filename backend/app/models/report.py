import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, now_ts, uuid_pk
from app.models.numbering import JsonB


class ReportExport(Base):
    __tablename__ = "report_exports"

    id: Mapped[uuid.UUID] = uuid_pk()
    report_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    template: Mapped[str] = mapped_column(String, nullable=False)
    content_snapshot: Mapped[dict] = mapped_column(JsonB, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = now_ts()
