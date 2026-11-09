# PLM Studio

In-house PLM with an AI prompt layer. Parts, revisions, multi-level BOMs,
documents (vector/JPEG/CAD) with a preview pipeline, ECR/ECO workflow,
audit trail and versioned PDF reports.

The full blueprint (architecture, ER model, milestones M0-M7) lives in the
project document "PLM-System Blueprint". Rules for agents:
[AGENTS.md](AGENTS.md) and [docs/api-contract.md](docs/api-contract.md).

## Status

- [x] M0 Repo, Docker Compose, CI
- [x] M1 Data model and Alembic migrations (schema incl. immutability trigger,
      workflow matrix, classes/number ranges as seed data; constraint tests)
- [x] M2 Parts, revisions, number ranges (duplicate check 409, released
      immutable via trigger + service check, audit log on every write)
- [x] M3 BOM and where-used (recursive CTE, BOM diff added/removed/changed)
- [x] M4 Documents and preview pipeline (upload/download, browser-native SVG/PDF, thumbnail/convert queue via preview_jobs + worker; originals immutable)
- [x] M5 ECR/ECO endpoints (ECR open->in_review->approved/rejected, ECO draft->approved->executed,
      affected part revisions on the ECO, confirmation-token path for all writes; models + matrix were already in place)
- [ ] M6 Report engine (Typst)
- [ ] M7 AI layer (LiteLLM, tools from /openapi.json, guardrails)

## Quickstart

    cp .env.example .env
    docker compose up -d db
    cd backend
    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    alembic upgrade head
    uvicorn app.main:app --reload
    # API docs: http://localhost:8000/docs

Tests (run locally on SQLite, no Docker):

    cd backend && pytest
    # against Postgres (trigger test): TEST_DATABASE_URL=... pytest

See [docs/runbooks/test-phase1.md](docs/runbooks/test-phase1.md) for the full
test walkthrough.

## API overview (Phase 1, /api/v1)

- `POST /auth/login`, `POST /auth/refresh` (HttpOnly cookie), roles viewer/editor/approver/admin
- `GET/POST /parts` (POST without `direct=true` -> 202 + confirmation token)
- `POST /parts/{pn}/revisions`, `POST /revisions/{id}/transition` (matrix + role, else 422/403)
- `GET/POST/PUT/DELETE /bom/...`, `GET /bom/parts/{pn}/where-used`, `GET /bom/parts/{pn}/diff`
- `POST /confirmations/{id}/approve|reject`
- `GET/POST /documents`, `POST /documents/{nr}/revisions`, `.../files` (upload), `/links`, `GET /doc-files/{id}/download|preview`, `POST /doc-revisions/{id}/transition`
- `GET/POST /ecrs`, `GET /ecrs/{nr}`, `POST /ecrs/{nr}/transition`, `POST /ecrs/{nr}/ecos`, `GET /ecos`, `GET /ecos/{nr}`, `POST /ecos/{nr}/transition`, `POST/DELETE /ecos/{nr}/affected-revisions[...]` (ECO only from an approved ECR; affected revisions editable only in draft)
- `GET /admin/health`, `/admin/number-ranges`, `/admin/part-classes`, `/admin/audit-log` (admin)

## Core principles

1. The LLM never touches the DB directly, only tool functions of the PLM API.
2. Writes go through confirmation tokens.
3. Released revisions are immutable (the DB trigger enforces it).
4. Every change lands in the append-only audit log.
5. Workflow transitions are rows in workflow_transitions, not code branches.

Decisions and rationale: docs/adr/. Number ranges: docs/number-ranges.md.
Runbooks: docs/runbooks/.

## Structure

    backend/    FastAPI app + Alembic + tests (app/{core,models,schemas,api,services,guardrails})
    frontend/   SvelteKit (skeleton; routes /parts, /bom, ... from M2-M6)
    agent/      LiteLLM config, system prompt, tool generation from /openapi.json (M7)
    previews/   Preview worker (libvips/Inkscape headless, M4)
    docs/       api-contract, number-ranges, adr, runbooks
