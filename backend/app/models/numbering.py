import uuid

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk

JsonB = JSON().with_variant(JSONB(), "postgresql")

ATTRIBUTE_TYPES = ("string", "number", "boolean", "enum")


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
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("part_classes.id"), nullable=True)


class ClassAttribute(Base):
    """Typed attribute definition per part class (ADR 0002)."""

    __tablename__ = "class_attributes"
    __table_args__ = (
        UniqueConstraint("class_id", "key", name="uq_class_attribute_key"),
        CheckConstraint(
            "attr_type IN ('string','number','boolean','enum')",
            name="class_attributes_type_valid",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("part_classes.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    attr_type: Mapped[str] = mapped_column(String, nullable=False, default="string")
    unit_code: Mapped[str | None] = mapped_column(ForeignKey("units.code"), nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allowed_values: Mapped[list | None] = mapped_column(JsonB, nullable=True)
