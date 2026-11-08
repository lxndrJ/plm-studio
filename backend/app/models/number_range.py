from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NumberRange(Base):
    __tablename__ = "number_ranges"

    prefix: Mapped[str] = mapped_column(String, primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, default=1)
    padding: Mapped[int] = mapped_column(Integer, default=6)
