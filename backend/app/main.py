from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app.api import admin, auth, bom, confirmations, documents, parts, revisions
from app.core import security
from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.core.errors import register_error_handlers
from app.models import Base
from app.models.user import User
from app.services.seed import seed_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_all(db)
        if db.execute(select(User.id).limit(1)).first() is None:
            admin_user = User(
                email=settings.BOOTSTRAP_ADMIN_EMAIL,
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
app.include_router(confirmations.router, prefix=API)
app.include_router(admin.router, prefix=API)


@app.get("/health")
def health():
    # kept minimal on purpose: no DB roundtrip here, so health checks stay
    # cheap and work before migrations ran (DB detail: GET /api/v1/admin/health)
    return {"status": "ok"}


@app.get("/")
def root():
    return {"name": "PLM-Studio API", "docs": "/docs", "openapi": "/openapi.json", "api": API}
