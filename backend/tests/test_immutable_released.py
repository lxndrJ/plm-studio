import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

DB_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DB_URL, reason="TEST_DATABASE_URL nicht gesetzt (Postgres noetig)"
)


def test_released_revision_is_immutable() -> None:
    """M1-Abnahmekriterium: Trigger blockiert UPDATE/DELETE auf released Revs."""
    engine = create_engine(DB_URL)
    uid = uuid.uuid4().hex[:8]

    with engine.begin() as conn:
        class_id = conn.execute(
            text("SELECT id FROM part_classes LIMIT 1")
        ).scalar_one()
        part_id = conn.execute(
            text(
                "INSERT INTO parts (part_number, name, part_type, class_id) "
                "VALUES (:pn, :name, 'part', :cls) RETURNING id"
            ),
            {"pn": f"P-TEST-{uid}", "name": f"Immutability-Test {uid}", "cls": class_id},
        ).scalar_one()
        rev_id = conn.execute(
            text(
                "INSERT INTO part_revisions (part_id, revision, status, change_reason, created_by) "
                "VALUES (:pid, '01', 'released', 'testfreigabe', "
                "'00000000-0000-0000-0000-000000000001') RETURNING id"
            ),
            {"pid": part_id},
        ).scalar_one()

    with pytest.raises(Exception, match="immutable"), engine.begin() as conn:
        conn.execute(
            text("UPDATE part_revisions SET change_reason = 'hack' WHERE id = :rid"),
            {"rid": rev_id},
        )

    # cleanup is best-effort: a released revision is immutable (trigger blocks
    # its DELETE) and the FK from part_revisions blocks deleting the part, so
    # on Postgres the row simply stays in the throwaway test DB
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM parts WHERE id = :pid"), {"pid": part_id})
    except SQLAlchemyError:
        pass


def test_workflow_transition_matrix_enforced() -> None:
    """M5-Vorbereitung: nur registrierte Spruenge existieren."""
    engine = create_engine(DB_URL)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT from_status, to_status FROM workflow_transitions "
                "WHERE entity_type = 'part_revision'"
            )
        ).all()
    pairs = {(r[0], r[1]) for r in rows}
    assert ("draft", "released") not in pairs, "draft darf nicht direkt released werden"
    assert ("review", "released") in pairs
