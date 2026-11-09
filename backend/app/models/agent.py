import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, now_ts, uuid_pk
from app.models.numbering import JsonB

MESSAGE_ROLES = ("user", "assistant", "tool", "system")


class AgentConversation(Base):
    """Chat conversation of the AI agent layer (M10), owned by a user."""

    __tablename__ = "agent_conversations"

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = now_ts()

    messages = relationship(
        "AgentMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AgentMessage.created_at",
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user','assistant','tool','system')", name="agent_messages_role_valid"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[dict] = mapped_column(JsonB, nullable=False, default=dict)
    created_at: Mapped[datetime] = now_ts()

    conversation = relationship("AgentConversation", back_populates="messages")
