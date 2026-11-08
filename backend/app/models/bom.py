import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid_pk


class BomItem(Base):
    __tablename__ = "bom_items"
    __table_args__ = (
        CheckConstraint("parent_rev_id <> component_rev_id", name="bom_no_self_reference"),
        UniqueConstraint("parent_rev_id", "position", name="uq_bom_position"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    parent_rev_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("part_revisions.id", ondelete="CASCADE"), nullable=False, index=True)
    component_rev_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("part_revisions.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False, default="Stk")
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    parent_rev = relationship("PartRevision", foreign_keys=[parent_rev_id])
    component_rev = relationship("PartRevision", foreign_keys=[component_rev_id])
