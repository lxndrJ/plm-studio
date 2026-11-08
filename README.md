# PLM Studio

Eigenbau-PLM mit KI-Prompt-Layer. Artikel, Revisionen, mehrstufige
Stuecklisten, Dokumente (Vector/JPEG/CAD) mit Preview-Pipeline,
ECR/ECO-Workflow, Audit-Trail und versionierten PDF-Reports.

Der vollstaendige Blueprint (Architektur, ER-Modell, Milestones M0-M7)
liegt im Projektdokument "PLM-System Blueprint". Regeln fuer Agenten:
[AGENTS.md](AGENTS.md) und [docs/api-contract.md](docs/api-contract.md).

## Status

- [x] M0 Repo, Docker Compose, CI
- [x] M1 Datenmodell und Alembic-Migrationen (Schema inkl. Immutability-Trigger,
      Workflow-Matrix, Klassen/Nummernkreisen als Seed-Daten; Constraint-Tests)
- [x] M2 Artikel, Revisionen, Nummernkreis (Duplikatpruefung 409, released
      immutable via Trigger + Service-Check, Audit-Log bei jedem Schreibvorgang)
- [x] M3 BOM und Where-Used (rekursives CTE, BOM-Diff added/removed/changed)
- [ ] M4 Dokumente und Preview-Pipeline (Modelle/Migration liegen bereit)
- [ ] M5 Workflow-API, ECR/ECO (Matrix + Modelle liegen bereit; Transition-API fuer part_revision ist live)
- [ ] M6 Report-Engine (Typst)
- [ ] M7 KI-Layer (LiteLLM, Tools aus /openapi.json, Guardrails)

## Quickstart

    cp .env.example .env
    docker compose up -d db
    cd backend
    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    alembic upgrade head
    uvicorn app.main:app --reload
    # API-Dokumentation: http://localhost:8000/docs

Tests (laufen lokal auf SQLite, ohne Docker):

    cd backend && pytest
    # gegen Postgres (Trigger-Test): TEST_DATABASE_URL=... pytest

## API-Ueberblick (Phase 1, /api/v1)

- `POST /auth/login`, `POST /auth/refresh` (HttpOnly-Cookie), Rollen viewer/editor/approver/admin
- `GET/POST /parts` (POST ohne `direct=true` -> 202 + Confirmation-Token)
- `POST /parts/{pn}/revisions`, `POST /revisions/{id}/transition` (Matrix + Rolle, sonst 422/403)
- `GET/POST/PUT/DELETE /bom/...`, `GET /bom/parts/{pn}/where-used`, `GET /bom/parts/{pn}/diff`
- `POST /confirmations/{id}/approve|reject`
- `GET /admin/health`, `/admin/number-ranges`, `/admin/part-classes`, `/admin/audit-log` (admin)

## Kernprinzipien

1. Das LLM ruft nie direkt die DB auf, nur Tool-Funktionen der PLM-API.
2. Schreibende Operationen laufen ueber Confirmation-Tokens.
3. Freigegebene Revisionen sind immutable (DB-Trigger erzwingt es).
4. Jede Aenderung landet im append-only Audit-Log.
5. Workflow-Spruenge sind Datensaetze in workflow_transitions, nicht Code.

Entscheidungen und Begruendungen: docs/adr/. Nummernkreise: docs/number-ranges.md.
Runbooks: docs/runbooks/.

## Struktur

    backend/    FastAPI-App + Alembic + Tests (app/{core,models,schemas,api,services,guardrails})
    frontend/   SvelteKit (Skelett; Routen /parts, /bom, ... ab M2-M6)
    agent/      LiteLLM-Config, System-Prompt, Tool-Generierung aus /openapi.json (M7)
    previews/   Preview-Worker (libvips/Inkscape headless, M4)
    docs/       api-contract, number-ranges, adr, runbooks
