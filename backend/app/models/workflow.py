import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk

# DB-driven transition matrix. Seeded by Alembic migration 0001 and used by the
# workflow guardrail: a status jump is only possible if a row exists here and
# the caller's role satisfies required_role.
DEFAULT_TRANSITIONS = [
    # entity_type, from_status, to_status, required_role
    ("part_revision", "draft", "review", "editor"),
    ("part_revision", "review", "draft", "approver"),
    ("part_revision", "review", "released", "approver"),
    ("part_revision", "released", "obsolete", "approver"),
    ("part_revision", "draft", "obsolete", "approver"),
    ("doc_revision", "draft", "review", "editor"),
    ("doc_revision", "review", "released", "approver"),
    ("doc_revision", "released", "obsolete", "approver"),
    ("ecr", "open", "in_review", "editor"),
    ("ecr", "in_review", "approved", "approver"),
    ("ecr", "in_review", "rejected", "approver"),
    ("eco", "draft", "approved", "approver"),
    ("eco", "approved", "executed", "approver"),
]


class WorkflowTransition(Base):
    __tablename__ = "workflow_transitions"

    id: Mapped[uuid.UUID] = uuid_pk()
    entity_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    from_status: Mapped[str] = mapped_column(String, nullable=False)
    to_status: Mapped[str] = mapped_column(String, nullable=False)
    required_role: Mapped[str] = mapped_column(String, nullable=False)
