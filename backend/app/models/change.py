import uuid
from datetime import datetime

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, now_ts, uuid_pk

eco_part_revisions = Table(
    "eco_part_revisions",
    Base.metadata,
    Column("eco_id", ForeignKey("ecos.id"), primary_key=True),
    Column("part_revision_id", ForeignKey("part_revisions.id"), primary_key=True),
)


class Ecr(Base):
    __tablename__ = "ecrs"

    id: Mapped[uuid.UUID] = uuid_pk()
    number: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    created_at: Mapped[datetime] = now_ts()

    ecos = relationship("Eco", back_populates="ecr", cascade="all, delete-orphan")


class Eco(Base):
    __tablename__ = "ecos"

    id: Mapped[uuid.UUID] = uuid_pk()
    number: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    ecr_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ecrs.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    created_at: Mapped[datetime] = now_ts()

    ecr = relationship("Ecr", back_populates="ecos")
    affected_revisions = relationship("PartRevision", secondary=eco_part_revisions)
