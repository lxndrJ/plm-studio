from fastapi import FastAPI

from app.api import health, parts


def create_app() -> FastAPI:
    app = FastAPI(title="PLM Studio API", version="0.1.0")
    app.include_router(health.router)
    app.include_router(parts.router, prefix="/api/v1/parts", tags=["parts"])
    return app


app = create_app()
