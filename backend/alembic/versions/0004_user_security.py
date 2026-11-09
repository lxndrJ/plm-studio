"""M8 user security: users.is_active + users.password_changed_at, revoked_tokens
denylist (logout revocation; jti-based)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _uuid():
    return UUID if _is_pg() else sa.types.Uuid()


def _pk_uuid():
    return {"server_default": sa.text("gen_random_uuid()")} if _is_pg() else {}


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    if _is_pg():
        op.add_column(
            "users",
            sa.Column(
                "password_changed_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
    else:
        # SQLite forbids non-constant defaults in ALTER TABLE ADD COLUMN
        op.add_column(
            "users",
            sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.execute("UPDATE users SET password_changed_at = datetime('now')")
    op.create_table(
        "revoked_tokens",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("jti", sa.String(), nullable=False),
        sa.Column("token_type", sa.String(), nullable=False),
        sa.Column("user_id", _uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "revoked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revoked_tokens_jti", "revoked_tokens", ["jti"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_revoked_tokens_jti", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "is_active")
