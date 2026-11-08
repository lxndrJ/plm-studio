"""initial schema (M1): full Phase-1 data model + released-immutability trigger + workflow matrix/class/range seeds

Revision ID: 0001
Revises:
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.models.workflow import DEFAULT_TRANSITIONS

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
UUID = postgresql.UUID(as_uuid=True)

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _uuid():
    return UUID if _is_pg() else sa.types.Uuid()


def _pk_uuid():
    # raw SQL inserts (runbooks, CI tests) rely on gen_random_uuid() on Postgres
    return {"server_default": sa.text("gen_random_uuid()")} if _is_pg() else {}


def _jsonb():
    return JSONB if _is_pg() else sa.JSON()


def _json_default():
    return {"server_default": sa.text("'{}'::jsonb" if _is_pg() else "'{}'")}


def _ts():
    return {"server_default": sa.func.now()}


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="viewer"),
        sa.CheckConstraint("role IN ('viewer','editor','approver','admin')", name="users_role_valid"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "number_ranges",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("code", sa.String(), nullable=False, unique=True),
        sa.Column("prefix", sa.String(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("next_number", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_number_ranges_code", "number_ranges", ["code"], unique=True)

    op.create_table(
        "part_classes",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("code", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("default_attributes", _jsonb(), nullable=False, **_json_default()),
    )
    op.create_index("ix_part_classes_code", "part_classes", ["code"], unique=True)

    op.create_table(
        "parts",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("part_number", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("part_type", sa.String(), nullable=False, server_default="part"),
        sa.Column("class_id", _uuid(), sa.ForeignKey("part_classes.id"), nullable=False),
        sa.Column("attributes", _jsonb(), nullable=False, **_json_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, **_ts()),
        sa.CheckConstraint("part_type IN ('part','assembly')", name="parts_type_valid"),
    )
    op.create_index("ix_parts_part_number", "parts", ["part_number"], unique=True)

    op.create_table(
        "part_revisions",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("part_id", _uuid(), sa.ForeignKey("parts.id"), nullable=False),
        sa.Column("revision", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("change_reason", sa.String(), nullable=False),
        sa.Column("created_by", _uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, **_ts()),
        sa.UniqueConstraint("part_id", "revision", name="uq_part_revision"),
        sa.CheckConstraint("status IN ('draft','review','released','obsolete')", name="part_revisions_status_valid"),
    )
    op.create_index("ix_part_revisions_part_id", "part_revisions", ["part_id"])

    op.create_table(
        "bom_items",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("parent_rev_id", _uuid(), sa.ForeignKey("part_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_rev_id", _uuid(), sa.ForeignKey("part_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit", sa.String(), nullable=False, server_default="Stk"),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("parent_rev_id <> component_rev_id", name="bom_no_self_reference"),
        sa.UniqueConstraint("parent_rev_id", "position", name="uq_bom_position"),
    )
    op.create_index("ix_bom_items_parent_rev_id", "bom_items", ["parent_rev_id"])
    op.create_index("ix_bom_items_component_rev_id", "bom_items", ["component_rev_id"])

    op.create_table(
        "documents",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("doc_number", sa.String(), nullable=False, unique=True),
        sa.Column("doc_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
    )
    op.create_index("ix_documents_doc_number", "documents", ["doc_number"], unique=True)

    op.create_table(
        "doc_revisions",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("document_id", _uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("revision", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("change_reason", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, **_ts()),
    )
    op.create_index("ix_doc_revisions_document_id", "doc_revisions", ["document_id"])

    op.create_table(
        "doc_files",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("doc_rev_id", _uuid(), sa.ForeignKey("doc_revisions.id"), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("is_original", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("preview_file_id", _uuid(), sa.ForeignKey("doc_files.id"), nullable=True),
    )
    op.create_index("ix_doc_files_doc_rev_id", "doc_files", ["doc_rev_id"])

    op.create_table(
        "doc_links",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("document_id", _uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("part_id", _uuid(), sa.ForeignKey("parts.id"), nullable=False),
        sa.Column("link_type", sa.String(), nullable=False),
    )
    op.create_index("ix_doc_links_document_id", "doc_links", ["document_id"])
    op.create_index("ix_doc_links_part_id", "doc_links", ["part_id"])

    op.create_table(
        "ecrs",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("number", sa.String(), nullable=False, unique=True),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, **_ts()),
    )
    op.create_index("ix_ecrs_number", "ecrs", ["number"], unique=True)

    op.create_table(
        "ecos",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("number", sa.String(), nullable=False, unique=True),
        sa.Column("ecr_id", _uuid(), sa.ForeignKey("ecrs.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, **_ts()),
    )
    op.create_index("ix_ecos_number", "ecos", ["number"], unique=True)
    op.create_index("ix_ecos_ecr_id", "ecos", ["ecr_id"])

    op.create_table(
        "eco_part_revisions",
        sa.Column("eco_id", _uuid(), sa.ForeignKey("ecos.id"), primary_key=True),
        sa.Column("part_revision_id", _uuid(), sa.ForeignKey("part_revisions.id"), primary_key=True),
    )

    op.create_table(
        "workflow_transitions",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("from_status", sa.String(), nullable=False),
        sa.Column("to_status", sa.String(), nullable=False),
        sa.Column("required_role", sa.String(), nullable=False),
    )
    op.create_index("ix_workflow_transitions_entity_type", "workflow_transitions", ["entity_type"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("old_values", _jsonb(), nullable=True),
        sa.Column("new_values", _jsonb(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("user_id", _uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, **_ts()),
    )
    op.create_index("ix_audit_log_entity_type", "audit_log", ["entity_type"])
    op.create_index("ix_audit_log_entity_id", "audit_log", ["entity_id"])
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])

    op.create_table(
        "report_exports",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("report_id", sa.String(), nullable=False, unique=True),
        sa.Column("template", sa.String(), nullable=False),
        sa.Column("content_snapshot", _jsonb(), nullable=False, **_json_default()),
        sa.Column("created_by", _uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, **_ts()),
    )
    op.create_index("ix_report_exports_report_id", "report_exports", ["report_id"], unique=True)

    op.create_table(
        "confirmations",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("payload", _jsonb(), nullable=False, **_json_default()),
        sa.Column("status", sa.String(), nullable=False, server_default="proposed"),
        sa.Column("created_by", _uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, **_ts()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, **_ts()),
        sa.Column("resolved_by", _uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_confirmations_action", "confirmations", ["action"])
    op.create_index("ix_confirmations_status", "confirmations", ["status"])

    if _is_pg():
        op.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_mutation_of_released() RETURNS trigger AS $fn$
            BEGIN
              IF OLD.status = 'released' AND TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'released revision ist immutable: neue Revision anlegen';
              END IF;
              RETURN COALESCE(NEW, OLD);
            END $fn$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_immutable_released
            BEFORE UPDATE OR DELETE ON part_revisions
            FOR EACH ROW EXECUTE FUNCTION prevent_mutation_of_released();
            """
        )

    import uuid as uuidlib

    op.bulk_insert(
        sa.table(
            "users",
            sa.column("id", _uuid()),
            sa.column("email", sa.String()),
            sa.column("password_hash", sa.String()),
            sa.column("role", sa.String()),
        ),
        [
            {
                "id": uuidlib.UUID(SYSTEM_USER_ID),
                "email": "admin@plm.local",
                "password_hash": "seeded-no-login",
                "role": "admin",
            }
        ],
    )
    op.bulk_insert(
        sa.table(
            "part_classes",
            sa.column("id", _uuid()),
            sa.column("code", sa.String()),
            sa.column("name", sa.String()),
            sa.column("default_attributes", _jsonb()),
        ),
        [
            {"id": uuidlib.uuid4(), "code": "MECH", "name": "Mechanik", "default_attributes": {"material": "", "weight_kg": None}},
            {"id": uuidlib.uuid4(), "code": "ELEC", "name": "Elektronik", "default_attributes": {"voltage_v": None}},
            {"id": uuidlib.uuid4(), "code": "CONS", "name": "Consumables", "default_attributes": {"supplier": ""}},
            {"id": uuidlib.uuid4(), "code": "PACK", "name": "Verpackung", "default_attributes": {"material": ""}},
        ],
    )
    op.bulk_insert(
        sa.table(
            "number_ranges",
            sa.column("id", _uuid()),
            sa.column("code", sa.String()),
            sa.column("prefix", sa.String()),
            sa.column("width", sa.Integer()),
            sa.column("next_number", sa.Integer()),
        ),
        [
            {"id": uuidlib.uuid4(), "code": "PART", "prefix": "P-", "width": 6, "next_number": 1},
            {"id": uuidlib.uuid4(), "code": "ASM", "prefix": "ASM-", "width": 6, "next_number": 1},
            {"id": uuidlib.uuid4(), "code": "DOC", "prefix": "DOC-", "width": 6, "next_number": 1},
            {"id": uuidlib.uuid4(), "code": "ECR", "prefix": "ECR-", "width": 5, "next_number": 1},
            {"id": uuidlib.uuid4(), "code": "ECO", "prefix": "ECO-", "width": 5, "next_number": 1},
            {"id": uuidlib.uuid4(), "code": "RPT", "prefix": "RPT-", "width": 5, "next_number": 1},
        ],
    )
    op.bulk_insert(
        sa.table(
            "workflow_transitions",
            sa.column("id", _uuid()),
            sa.column("entity_type", sa.String()),
            sa.column("from_status", sa.String()),
            sa.column("to_status", sa.String()),
            sa.column("required_role", sa.String()),
        ),
        [
            {"id": uuidlib.uuid4(), "entity_type": et, "from_status": f, "to_status": t, "required_role": r}
            for et, f, t, r in DEFAULT_TRANSITIONS
        ],
    )


def downgrade() -> None:
    if _is_pg():
        op.execute("DROP TRIGGER IF EXISTS trg_immutable_released ON part_revisions;")
        op.execute("DROP FUNCTION IF EXISTS prevent_mutation_of_released();")
    # drop in reverse-dependency order: dependents first, users last
    for table in [
        "confirmations",
        "report_exports",
        "audit_log",
        "workflow_transitions",
        "eco_part_revisions",
        "ecos",
        "ecrs",
        "doc_links",
        "doc_files",
        "doc_revisions",
        "documents",
        "bom_items",
        "part_revisions",
        "parts",
        "part_classes",
        "number_ranges",
        "users",
    ]:
        op.drop_table(table)
