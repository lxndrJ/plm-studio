# Runbook: Setup

## Local (development)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL="postgresql+psycopg://plm:plm@localhost:5432/plm"  # or sqlite:///./dev.db
alembic upgrade head          # migrations
uvicorn app.main:app --reload --port 8000
```

On first start the app creates the bootstrap admin
(`BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` from the environment).
Afterwards create more users as admin: `POST /api/v1/auth/users`.

Tests: `pytest` (run on SQLite, no Docker).

## VPS (production)

```bash
cp .env.example .env   # set passwords / JWT secret
 docker compose up -d --build
docker compose exec api alembic upgrade head
```

- Reverse proxy (Caddy or Traefik) in front, TLS automatic. In code the
  refresh cookie uses `secure=False` — set it to `True` behind HTTPS.
- Expose only ports 80/443 of the proxy; keep 8000/4000/5432 internal.
