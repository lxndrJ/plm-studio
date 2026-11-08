import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WorkflowTransition(Base):
    __tablename__ = "workflow_transitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String)
    from_status: Mapped[str] = mapped_column(String)
    to_status: Mapped[str] = mapped_column(String)
    required_role: Mapped[str] = mapped_column(String)
