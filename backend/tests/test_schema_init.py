from sqlalchemy import create_engine, inspect, text

from app.main import ensure_schema
from app.models import Base


def test_ensure_schema_runs_alembic_on_empty_db(tmp_path):
    url = f"sqlite:///{tmp_path}/fresh.db"
    engine = create_engine(url)
    ensure_schema(engine, url)
    insp = inspect(engine)
    assert insp.has_table("users")
    assert insp.has_table("alembic_version")
    with engine.connect() as c:
        assert c.execute(text("select version_num from alembic_version")).scalar() == "0003"


def test_ensure_schema_is_noop_when_tables_already_exist(tmp_path):
    url = f"sqlite:///{tmp_path}/pre.db"
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    ensure_schema(engine, url)
    assert not inspect(engine).has_table("alembic_version")
    assert inspect(engine).has_table("users")
