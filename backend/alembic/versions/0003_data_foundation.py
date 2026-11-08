"""data foundation (M1.5): units master data, class hierarchy, typed class
attributes, revision-scoped attributes (ADR 0002)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
UUID = postgresql.UUID(as_uuid=True)

DEFAULT_UNITS = [
    ("Stk", "Stueck", "count"),
    ("m", "Meter", "length"),
    ("mm", "Millimeter", "length"),
    ("kg", "Kilogramm", "mass"),
    ("g", "Gramm", "mass"),
    ("l", "Liter", "volume"),
    ("s", "Sekunde", "time"),
]

# (code, name, parent_code)
DEFAULT_SUBCLASSES = [
    ("FAS", "Fastening technology", "MECH"),
    ("PCB", "Leiterplatten", "ELEC"),
]

# (class_code, key, label, attr_type, unit_code, required, allowed_values)
DEFAULT_CLASS_ATTRIBUTES = [
    ("MECH", "material", "Material", "string", None, False, None),
    ("MECH", "weight_kg", "Gewicht", "number", "kg", False, None),
    ("ELEC", "voltage_v", "Nennspannung", "number", None, False, None),
    ("ELEC", "ip_rating", "Schutzart", "enum", None, False, ["IP20", "IP54", "IP65", "IP67"]),
    ("CONS", "supplier", "Lieferant", "string", None, False, None),
    ("PACK", "material", "Material", "string", None, False, None),
]


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _uuid():
    return UUID if _is_pg() else sa.types.Uuid()


def _pk_uuid():
    return {"server_default": sa.text("gen_random_uuid()")} if _is_pg() else {}


def _jsonb():
    return JSONB if _is_pg() else sa.JSON()


def _json_default():
    return {"server_default": sa.text("'{}'::jsonb" if _is_pg() else "'{}'")}


def upgrade() -> None:
    import uuid as uuidlib

    conn = op.get_bind()

    # 1) units master data (natural key `code`)
    op.create_table(
        "units",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("dimension", sa.String(), nullable=False, server_default="other"),
        sa.CheckConstraint(
            "dimension IN ('count','length','mass','volume','area','time','other')",
            name="units_dimension_valid",
        ),
    )
    units_t = sa.table(
        "units",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("dimension", sa.String()),
    )
    for code, name, dimension in DEFAULT_UNITS:
        exists = conn.execute(sa.select(units_t.c.code).where(units_t.c.code == code)).first()
        if not exists:
            conn.execute(units_t.insert(), {"code": code, "name": name, "dimension": dimension})

    # 2) BOM units reference the master data: data fix first, then FK
    op.execute("UPDATE bom_items SET unit = 'Stk' WHERE unit NOT IN (SELECT code FROM units)")
    with op.batch_alter_table("bom_items") as batch_op:
        batch_op.create_foreign_key("fk_bom_items_unit", "units", ["unit"], ["code"])

    # 3) typed attribute definitions per class
    op.create_table(
        "class_attributes",
        sa.Column("id", _uuid(), primary_key=True, **_pk_uuid()),
        sa.Column("class_id", _uuid(), sa.ForeignKey("part_classes.id"), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("attr_type", sa.String(), nullable=False, server_default="string"),
        sa.Column("unit_code", sa.String(), sa.ForeignKey("units.code"), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allowed_values", _jsonb(), nullable=True),
        sa.UniqueConstraint("class_id", "key", name="uq_class_attribute_key"),
        sa.CheckConstraint(
            "attr_type IN ('string','number','boolean','enum')",
            name="class_attributes_type_valid",
        ),
    )
    op.create_index("ix_class_attributes_class_id", "class_attributes", ["class_id"])

    # 4) class hierarchy (self-referencing tree)
    with op.batch_alter_table("part_classes") as batch_op:
        batch_op.add_column(sa.Column("parent_id", _uuid(), nullable=True))
        batch_op.create_foreign_key("fk_part_classes_parent", "part_classes", ["parent_id"], ["id"])
    op.create_index("ix_part_classes_parent_id", "part_classes", ["parent_id"])

    # 5) revision-scoped attributes: add column, copy part-level attributes
    #    to every existing revision, then drop the part-level column
    with op.batch_alter_table("part_revisions") as batch_op:
        batch_op.add_column(sa.Column("attributes", _jsonb(), nullable=False, **_json_default()))
    op.execute(
        "UPDATE part_revisions SET attributes = "
        "(SELECT p.attributes FROM parts p WHERE p.id = part_revisions.part_id)"
    )
    with op.batch_alter_table("parts") as batch_op:
        batch_op.drop_column("attributes")

    # 6) seeds: subclasses + typed attribute definitions
    classes_t = sa.table(
        "part_classes",
        sa.column("id", _uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("default_attributes", _jsonb()),
        sa.column("parent_id", _uuid()),
    )
    class_ids = dict(conn.execute(sa.select(classes_t.c.code, classes_t.c.id)).fetchall())
    for code, name, parent_code in DEFAULT_SUBCLASSES:
        exists = conn.execute(sa.select(classes_t.c.id).where(classes_t.c.code == code)).first()
        if not exists:
            conn.execute(
                classes_t.insert(),
                {
                    "id": uuidlib.uuid4(),
                    "code": code,
                    "name": name,
                    "default_attributes": {},
                    "parent_id": class_ids[parent_code],
                },
            )
    class_ids = dict(conn.execute(sa.select(classes_t.c.code, classes_t.c.id)).fetchall())

    attrs_t = sa.table(
        "class_attributes",
        sa.column("id", _uuid()),
        sa.column("class_id", _uuid()),
        sa.column("key", sa.String()),
        sa.column("label", sa.String()),
        sa.column("attr_type", sa.String()),
        sa.column("unit_code", sa.String()),
        sa.column("required", sa.Boolean()),
        sa.column("allowed_values", _jsonb()),
    )
    for cls_code, key, label, attr_type, unit_code, required, allowed in DEFAULT_CLASS_ATTRIBUTES:
        class_id = class_ids.get(cls_code)
        if class_id is None:
            continue
        exists = conn.execute(
            sa.select(attrs_t.c.id).where(attrs_t.c.class_id == class_id, attrs_t.c.key == key)
        ).first()
        if not exists:
            conn.execute(
                attrs_t.insert(),
                {
                    "id": uuidlib.uuid4(),
                    "class_id": class_id,
                    "key": key,
                    "label": label,
                    "attr_type": attr_type,
                    "unit_code": unit_code,
                    "required": required,
                    "allowed_values": allowed,
                },
            )


def downgrade() -> None:
    conn = op.get_bind()

    # restore part-level attributes from the newest revision (best effort)
    with op.batch_alter_table("parts") as batch_op:
        batch_op.add_column(sa.Column("attributes", _jsonb(), nullable=False, **_json_default()))
    op.execute(
        "UPDATE parts SET attributes = ("
        "SELECT r.attributes FROM part_revisions r WHERE r.part_id = parts.id "
        "AND r.revision = (SELECT MAX(r2.revision) FROM part_revisions r2 "
        "WHERE r2.part_id = parts.id))"
    )
    with op.batch_alter_table("part_revisions") as batch_op:
        batch_op.drop_column("attributes")

    # typed attribute definitions
    op.drop_index("ix_class_attributes_class_id", table_name="class_attributes")
    op.drop_table("class_attributes")

    # hierarchy: seeded subclasses are removed best effort (only if unreferenced)
    op.drop_index("ix_part_classes_parent_id", table_name="part_classes")
    conn.execute(
        sa.text(
            "DELETE FROM part_classes WHERE code IN ('FAS','PCB') "
            "AND id NOT IN (SELECT class_id FROM parts)"
        )
    )
    with op.batch_alter_table("part_classes") as batch_op:
        batch_op.drop_constraint("fk_part_classes_parent", type_="foreignkey")
        batch_op.drop_column("parent_id")

    # units master data
    with op.batch_alter_table("bom_items") as batch_op:
        batch_op.drop_constraint("fk_bom_items_unit", type_="foreignkey")
    op.drop_table("units")
