import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, now_ts, uuid_pk
from app.models.numbering import JsonB

PART_TYPES = ("part", "assembly")
REVISION_STATUSES = ("draft", "review", "released", "obsolete")


class Part(Base):
    __tablename__ = "parts"
    __table_args__ = (
        CheckConstraint("part_type IN ('part','assembly')", name="parts_type_valid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    part_number: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    part_type: Mapped[str] = mapped_column(String, nullable=False, default="part")
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("part_classes.id"), nullable=False)
    created_at: Mapped[datetime] = now_ts()

    revisions = relationship("PartRevision", back_populates="part", cascade="all, delete-orphan")


class PartRevision(Base):
    __tablename__ = "part_revisions"
    __table_args__ = (
        UniqueConstraint("part_id", "revision", name="uq_part_revision"),
        CheckConstraint("status IN ('draft','review','released','obsolete')", name="part_revisions_status_valid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"), nullable=False, index=True)
    revision: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    change_reason: Mapped[str] = mapped_column(String, nullable=False)
    attributes: Mapped[dict] = mapped_column(JsonB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = now_ts()

    part = relationship("Part", back_populates="revisions")
