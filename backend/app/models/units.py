from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

UNIT_DIMENSIONS = ("count", "length", "mass", "volume", "area", "time", "other")


class Unit(Base):
    """Units master data (natural key `code`, e.g. Stk, m, kg)."""

    __tablename__ = "units"
    __table_args__ = (
        CheckConstraint(
            "dimension IN ('count','length','mass','volume','area','time','other')",
            name="units_dimension_valid",
        ),
    )

    code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    dimension: Mapped[str] = mapped_column(String, nullable=False, default="other")
