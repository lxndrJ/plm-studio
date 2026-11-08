import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PartClass(Base):
    __tablename__ = "part_classes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    default_attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    part_number: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    part_type: Mapped[str] = mapped_column(String)
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("part_classes.id"))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PartRevision(Base):
    __tablename__ = "part_revisions"
    __table_args__ = (UniqueConstraint("part_id", "revision"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    revision: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="draft")
    change_reason: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
