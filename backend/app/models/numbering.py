import uuid

from sqlalchemy import JSON, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk

JsonB = JSON().with_variant(JSONB(), "postgresql")


class NumberRange(Base):
    __tablename__ = "number_ranges"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    prefix: Mapped[str] = mapped_column(String, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    next_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class PartClass(Base):
    __tablename__ = "part_classes"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    default_attributes: Mapped[dict] = mapped_column(JsonB, nullable=False, default=dict)
