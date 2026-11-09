from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.part import Part
from app.services.testdata import SAISONS, TEST_CLASS_CODE, clear_test_data, seed_test_data
from tests.conftest import create_part


def _seed(count, seed):
    db = SessionLocal()
    try:
        return seed_test_data(db, count=count, seed=seed)
    finally:
        db.close()


def _snapshot():
    db = SessionLocal()
    try:
        parts = db.execute(select(Part).order_by(Part.name)).scalars().all()
        return [(p.name, dict(p.revisions[0].attributes)) for p in parts]
    finally:
        db.close()


def test_seed_creates_parts_separable_via_test_class(client, editor):
    stats = _seed(count=12, seed=7)
    assert stats["parts"] + stats["assemblies"] == 12
    assert stats["class_code"] == TEST_CLASS_CODE

    r = client.get(f"/api/v1/parts?class_code={TEST_CLASS_CODE}", headers=editor)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 12
    assert all(row["name"].startswith("TEST ") for row in rows)

    r = client.get("/api/v1/parts?query=TEST", headers=editor)
    assert len(r.json()) == 12

    detail = client.get(f"/api/v1/parts/{rows[0]['part_number']}", headers=editor).json()
    rev = detail["revisions"][0]
    assert rev["status"] == "draft"
    attrs = rev["attributes"]
    assert attrs["saison"] in SAISONS
    assert isinstance(attrs["farbe"], str) and attrs["farbe"]
    assert isinstance(attrs["preis"], (int, float)) and attrs["preis"] > 0
    assert "TESTDATENSATZ" in detail["description"]


def test_assemblies_have_bom_lines(client, editor):
    _seed(count=10, seed=3)
    rows = client.get(f"/api/v1/parts?class_code={TEST_CLASS_CODE}", headers=editor).json()
    assemblies = [r for r in rows if r["part_type"] == "assembly"]
    assert assemblies, "expected at least one assembly"
    assert all(a["part_number"].startswith("ASM-") for a in assemblies)
    for asm in assemblies:
        bom = client.get(f"/api/v1/bom/parts/{asm['part_number']}", headers=editor).json()
        assert 2 <= len(bom) <= 5
        assert all(item["unit"] == "Stk" for item in bom)
        assert all(item["component_status"] in ("draft", "released") for item in bom)
        assert all(item["component_part_number"].startswith("P-") for item in bom)


def test_seed_is_deterministic_for_same_seed(client, editor):
    _seed(count=8, seed=42)
    first = _snapshot()
    db = SessionLocal()
    try:
        clear_test_data(db)
    finally:
        db.close()
    _seed(count=8, seed=42)
    assert _snapshot() == first


def test_clear_removes_only_test_parts(client, editor):
    keep = create_part(client, editor, "Echtes Teil", class_code="MECH")
    _seed(count=6, seed=1)
    db = SessionLocal()
    try:
        removed = clear_test_data(db)
        remaining = [p.part_number for p in db.execute(select(Part)).scalars().all()]
    finally:
        db.close()
    assert removed == 6
    assert remaining == [keep["part_number"]]
    r = client.get(f"/api/v1/parts?class_code={TEST_CLASS_CODE}", headers=editor)
    assert r.json() == []
