import os
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import select

from alembic import command
from app.api import (
    admin,
    agent,
    auth,
    bom,
    changes,
    confirmations,
    documents,
    parts,
    reports,
    revisions,
)
from app.core import security
from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.core.errors import register_error_handlers
from app.models.user import User
from app.services.seed import seed_all


def bootstrap_admin_email(email: str) -> str:
    """The bootstrap admin email must pass the same EmailStr validation as the
    login endpoint — otherwise the user gets created but can never log in
    (email-validator rejects reserved/special-use domains like .local)."""
    from pydantic import EmailStr, TypeAdapter

    try:
        return str(TypeAdapter(EmailStr).validate_python(email))
    except Exception as e:
        raise RuntimeError(
            f"BOOTSTRAP_ADMIN_EMAIL '{email}' would be unusable at login (reserved/special-use domain?): {e}"
        ) from e


def ensure_schema(engine, database_url: str) -> None:
    """Schema exclusively via Alembic. On a completely empty DB (no tables and
    no alembic_version) migrations run programmatically; on an initialized DB
    this is a no-op. Never create_all here: that would create tables without
    an alembic_version row and break a later `alembic upgrade head` with
    DuplicateTable."""
    from sqlalchemy import inspect

    insp = inspect(engine)
    if insp.has_table("alembic_version") or insp.has_table("users"):
        return
    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    # alembic/env.py prefers the DATABASE_URL env var; pin it so the migration
    # always runs against the intended database
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        command.upgrade(cfg, "head")
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    ensure_schema(engine, settings.DATABASE_URL)
    db = SessionLocal()
    try:
        seed_all(db)
        if db.execute(select(User.id).limit(1)).first() is None:
            admin_user = User(
                email=bootstrap_admin_email(settings.BOOTSTRAP_ADMIN_EMAIL),
                password_hash=security.hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
                role="admin",
            )
            db.add(admin_user)
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(
    title="PLM-Studio API",
    version="0.1.0",
    description=(
        "In-house PLM. This API's OpenAPI schema is also the tool contract "
        "for the AI agent (phase 2). Write operations without direct=true return "
        "202 + confirmation token."
    ),
    lifespan=lifespan,
)

register_error_handlers(app)

API = "/api/v1"
app.include_router(auth.router, prefix=API)
app.include_router(parts.router, prefix=API)
app.include_router(revisions.router, prefix=API)
app.include_router(bom.router, prefix=API)
app.include_router(documents.router, prefix=API)
app.include_router(changes.router, prefix=API)
app.include_router(reports.router, prefix=API)
app.include_router(confirmations.router, prefix=API)
app.include_router(admin.router, prefix=API)
app.include_router(agent.router, prefix=API)


@app.get("/health")
def health():
    # kept minimal on purpose: no DB roundtrip here, so health checks stay
    # cheap and work before migrations ran (DB detail: GET /api/v1/admin/health)
    return {"status": "ok"}


@app.get("/")
def root():
    return {"name": "PLM-Studio API", "docs": "/docs", "openapi": "/openapi.json", "api": API}
