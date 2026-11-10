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
- [x] M6 Report engine (Typst): versioned PDF reports (`RPT-...`) with frozen `content_snapshot`,
      released-only content filter (internal attributes like preis/lieferant stripped), PDF download, confirmation-token path
- [x] M7 AI layer (agent/: tools generated from /openapi.json via `plm_agent.toolgen`,
      ReAct runner via LiteLLM, guardrails: no `direct` writes, never self-approve confirmations, 429/5xx backoff)
- [x] M8 Phase-2 security: user management (`GET/PATCH /auth/users`, deactivate, role change with
      self-lockout guard), password change + admin reset (token invalidation via password fingerprint),
      logout revokes access+refresh tokens (jti denylist, migration 0004), login rate limiting
      (429 + Retry-After, migration 0004, configurable via `LOGIN_RATE_LIMIT_*`) — all audited
- [x] M9 Phase-2 ECO execution: `approved -> executed` creates one successor draft revision per
      affected (released-only, 409 `affected_not_released`) part revision, inheriting attributes+BOM,
      `change_reason` references ECO/ECR, idempotent via the workflow matrix, fully audited;
      see docs/changes.md
- [x] M10 Phase-2 agent service: `agent/` runs as its own compose service (port 8001) with
      `POST /chat` (SSE stream: tool calls, 202 proposals, answer) and conversation persistence
      via `POST/GET /api/v1/agent/conversations*` (migration 0005, owner-scoped); CLI is a thin
      client with `--service-url`; `/api/v1/agent/*` is excluded from the LLM tool catalog
- [x] M11 Phase-2 UI/reports/export: `/agent` chat page (SSE stream, inline proposal approval),
      `/admin` page (users/roles/active, password reset, classes with typed attribute defs, audit
      log, stats), typed attribute form on part detail (`PATCH .../attributes`, draft-only),
      document preview pane, list pagination + type/status filters + CSV/JSON export
      (`/export/parts`, `/export/bom/{pn}`), BOM-explosion + ECR/ECO PDF report templates,
      confirmations badge in nav, `/admin/stats` now requires auth
- [x] Logs in der UI: `/logs`-Seite aggregiert die In-Memory-Ringbuffer aller Dienste
      (`GET /api/v1/admin/logs` [admin], `GET /agent-api/logs`, `GET /previews-api/logs` —
      Previews-Worker serviert dafür einen Mini-HTTP-Port 8002); `/agent`-Chat zeigt SSE-Error-Events
      als rote Bubbles + aufklappbares Event-Log
- [ ] Phase 3 (M12+): planned in [docs/phase-3.md](docs/phase-3.md)

## Quickstart

    cp .env.example .env
    docker compose up -d --build   # one-shot 'migrate' service runs alembic upgrade head before the API starts
    # UI: http://localhost:3000   |   API docs: http://localhost:8000/docs

Local without Docker:

    cd backend
    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    alembic upgrade head          # before the first app start (schema only via Alembic)
    uvicorn app.main:app --reload

Tests (run locally on SQLite, no Docker):

    cd backend && pytest
    # against Postgres (trigger test): TEST_DATABASE_URL=... pytest

Test data (dev/demo): deterministic, clearly separable records in the part
class `TEST` (name prefix `TEST `, attributes saison/farbe/preis, ~20%
assemblies with BOM lines; SKU = part number):

    cd backend && python -m app.services.testdata --count 200 [--levels 1] [--seed 42] [--reset]
    # bigger demo: --count 2000 --levels 3  (multi-level BOMs, assemblies in assemblies)
    # find them via GET /api/v1/parts?class_code=TEST or ?query=TEST
    # details: docs/runbooks/demo-data.md

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
- `POST /reports/parts/{pn}`, `GET /reports`, `GET /reports/{id}`, `GET /reports/{id}/download` (PDF via Typst; snapshot contains only released content, internal attributes stripped)
- `GET /admin/health`, `/admin/number-ranges`, `/admin/part-classes`, `/admin/audit-log` (admin)

## Core principles

1. The LLM never touches the DB directly, only tool functions of the PLM API.
2. Writes go through confirmation tokens.
3. Released revisions are immutable (the DB trigger enforces it).
4. Every change lands in the append-only audit log.
5. Workflow transitions are rows in workflow_transitions, not code branches.

Decisions and rationale: docs/adr/. Number ranges: docs/number-ranges.md.
Runbooks: docs/runbooks/.

## AI agent (M7)

    pip install -e "agent[dev]"
    # tool definitions from the running API schema:
    python -m plm_agent.toolgen --openapi http://localhost:8000/openapi.json   # writes agent/tools/tools.json
    # one prompt through the agent loop (env: PLM_API_URL, OPENAI_BASE_URL, OPENAI_API_KEY, LLM_MODEL, PLM_AGENT_EMAIL, PLM_AGENT_PASSWORD):
    python -m plm_agent "Suche alle TEST-Teile und lege 'Neues Teil' als Aenderungsvorschlag an"

The agent only calls documented API endpoints (tools from /openapi.json), writes
always come back as 202 + confirmation token and are approved by the human via
`POST /api/v1/confirmations/{id}/approve`.

### Agent service (M10)

    docker compose up -d agent        # http://localhost:8001
    curl -N -X POST http://localhost:8001/chat -H 'Content-Type: application/json' \
         -d '{"message": "Suche alle TEST-Teile"}'
    # SSE events: conversation -> tool_call* -> delta -> done -> end
    # CLI as thin client: AGENT_SERVICE_URL=http://localhost:8001 python -m plm_agent "..."

Conversations persist in the backend (`/api/v1/agent/conversations*`, migration 0005,
owned by the agent service account). If `AGENT_SERVICE_TOKEN` is set, clients must send
it as `X-Agent-Token`. The service is internal — do not expose it publicly.

LLM endpoint: default is the local LiteLLM proxy (`OPENAI_BASE_URL=http://litellm:4000/v1`,
`LLM_MODEL=plm-chat`). A direct provider also works — e.g. Mistral:
`OPENAI_BASE_URL=https://api.mistral.ai/v1`, `OPENAI_API_KEY=<key>`,
`LLM_MODEL=mistral-large-latest` (real keys only in the local `.env`, never committed;
see `.env.example`). The runner normalizes the base URL to `.../v1/chat/completions`.

## Updates & dependencies

- Python deps (`backend/pyproject.toml`), Docker base images and GitHub
  Actions are updated via Dependabot (`.github/dependabot.yml`, weekly PRs).
- Schema changes only via new Alembic migrations, never by hand in the DB.
- The Typst binary in `backend/Dockerfile` is pinned via `ARG TYPST_VERSION`;
  bump it deliberately together with a Typst release.

## Structure

    backend/    FastAPI app + Alembic + tests (app/{core,models,schemas,api,services,guardrails})
    frontend/   SvelteKit UI (Dashboard, Artikel, Stücklisten, ECR/ECO, Bestätigungen, Reports, Dokumente; Port 3000 via compose)
    agent/      LiteLLM config, system prompt, tool generation from /openapi.json (M7)
    previews/   Preview worker (libvips/Inkscape headless, M4)
    docs/       api-contract, number-ranges, adr, runbooks
