"""M1 acceptance: schema constraints exist and are enforced."""

import subprocess
import sys

import pytest
import sqlalchemy as sa

from app.models.bom import BomItem
from app.models.numbering import PartClass
from app.models.part import Part, PartRevision
from app.models.user import User


def test_unique_part_revision_enforced(client, db):
    user = db.execute(sa.select(User).where(User.role == "editor")).scalar_one()
    cls = db.execute(sa.select(PartClass)).scalars().first()
    part = Part(
        part_number="P-TEST",
        name="t",
        part_type="part",
        class_id=cls.id,
        attributes={},
    )
    db.add(part)
    db.flush()
    db.add(PartRevision(part_id=part.id, revision="01", status="draft", change_reason="x", created_by=user.id))
    db.commit()
    db.add(PartRevision(part_id=part.id, revision="01", status="draft", change_reason="dup", created_by=user.id))
    with pytest.raises(sa.exc.IntegrityError):
        db.commit()
    db.rollback()


def test_bom_self_reference_check_enforced(client, db):
    user = db.execute(sa.select(User).where(User.role == "editor")).scalar_one()
    cls = db.execute(sa.select(PartClass)).scalars().first()
    part = Part(part_number="P-SELF", name="s", part_type="assembly", class_id=cls.id, attributes={})
    db.add(part)
    db.flush()
    rev = PartRevision(part_id=part.id, revision="01", status="draft", change_reason="x", created_by=user.id)
    db.add(rev)
    db.flush()
    db.add(BomItem(parent_rev_id=rev.id, component_rev_id=rev.id, quantity=1, unit="Stk", position=1))
    with pytest.raises(sa.exc.IntegrityError):
        db.commit()
    db.rollback()


def test_alembic_up_down_on_empty_db(tmp_path):
    """M1: migrations run up and down cleanly."""
    import os

    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{tmp_path}/mig.db"
    backend_dir = str(__import__("pathlib").Path(__file__).resolve().parent.parent)
    up = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir, env=env, capture_output=True, text=True, check=False,
    )
    assert up.returncode == 0, up.stderr
    down = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=backend_dir, env=env, capture_output=True, text=True, check=False,
    )
    assert down.returncode == 0, down.stderr


def test_audit_log_is_append_only_via_api(client, editor, admin):
    """No mutating endpoints exist for audit_log: PUT/DELETE/PATCH are 405."""
    for method in ("put", "delete", "patch"):
        r = getattr(client, method)("/api/v1/admin/audit-log", headers=admin)
        assert r.status_code == 405
    from tests.conftest import create_part

    create_part(client, editor, "Audit-Teil")
    log = client.get("/api/v1/admin/audit-log", headers=admin).json()
    assert any(e["entity_type"] == "part" and e["action"] == "create" for e in log)
    r = client.get("/api/v1/admin/audit-log", headers=editor)
    assert r.status_code == 403
