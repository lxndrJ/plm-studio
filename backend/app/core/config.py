from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://plm:plm@localhost:5432/plm"
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_MINUTES: int = 30
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@example.com"
    BOOTSTRAP_ADMIN_PASSWORD: str = "admin"
    STORAGE_DIR: str = "./data/files"
    CONFIRMATION_TTL_HOURS: int = 24
    TYPST_BINARY: str = "typst"


@lru_cache
def get_settings() -> Settings:
    return Settings()
