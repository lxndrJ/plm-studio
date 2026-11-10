"""M10 agent service: conversation persistence (agent_conversations, agent_messages)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
UUID = postgresql.UUID(as_uuid=True)


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _uuid():
    return UUID if _is_pg() else sa.types.Uuid()


def _pk_uuid():
    return {"server_default": sa.text("gen_random_uuid()")} if _is_pg() else {}


def _jsonb():
    return JSONB if _is_pg() else sa.JSON()


def _json_default():
    return {"server_default": sa.text("'[]'::jsonb" if _is_pg() else "'[]'")}


def upgrade() -> None:
    op.create_table(
        "agent_conversations",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("created_by", _uuid(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "agent_messages",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column(
            "conversation_id",
            _uuid(),
            sa.ForeignKey("agent_conversations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", _jsonb(), nullable=False, **_json_default()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "role IN ('user','assistant','tool','system')", name="agent_messages_role_valid"
        ),
    )


def downgrade() -> None:
    op.drop_table("agent_messages")
    op.drop_table("agent_conversations")
