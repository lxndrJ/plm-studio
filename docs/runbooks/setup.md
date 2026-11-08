# Runbook: Setup

## Lokal (Entwicklung)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL="postgresql+psycopg://plm:plm@localhost:5432/plm"  # oder sqlite:///./dev.db
alembic upgrade head          # Migrationen
uvicorn app.main:app --reload --port 8000
```

Beim ersten Start legt die App den Bootstrap-Admin an
(`BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` aus der Umgebung).
Danach weitere User als Admin: `POST /api/v1/auth/users`.

Tests: `pytest` (laufen auf SQLite, ohne Docker).

## VPS (Produktiv)

```bash
cp .env.example .env   # Passwörter/JWT-Secret setzen
 docker compose up -d --build
docker compose exec api alembic upgrade head
```

- Reverse Proxy (Caddy oder Traefik) davor, TLS automatisch. Im Code ist
  `secure=False` für das Refresh-Cookie — hinter HTTPS auf `True` stellen.
- Nur Port 80/443 des Proxys nach außen; 8000/4000/5432 intern.

## Raspberry Pi (Test)

Gleiche Compose-Datei; Images sind multi-arch (postgres:16-alpine,
python:3.12-slim, litellm). Preview-Worker und LiteLLM optional weglassen,
wenn RAM knapp: `docker compose up -d db api`.
