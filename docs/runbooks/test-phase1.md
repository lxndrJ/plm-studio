# Runbook: Testing Phase 1 (M1-M3)

How to verify the first implemented section (parts, revisions, BOM, confirmations,
workflow, audit) — automated first, then a manual API smoke test.

## 1. Automated checks (local, no Docker needed)

```bash
cd backend
pip install -e ".[dev]"
pytest                          # 38 tests on SQLite
ruff check backend              # lint rule from AGENTS.md
alembic upgrade head            # migration up
alembic downgrade base          # and back down (M1 acceptance criterion)
alembic upgrade head
```

Test-to-milestone mapping:

| Milestone | Tests |
|---|---|
| M1 schema/constraints | `tests/test_constraints.py` — unique `(part_id, revision)`, BOM self-reference, alembic up/down, audit log append-only |
| M2 parts/revisions | `tests/test_parts.py`, `tests/test_revisions_workflow.py` — duplicate 409, released immutable, audit entries |
| M3 BOM | `tests/test_bom.py` — recursive where-used over 3 levels, BOM diff added/removed/changed |
| M4 documents/preview | `tests/test_documents.py` — upload/download byte-identical, PNG thumbnail derivative without manual step, native SVG preview, originals immutable (405), released doc rev 409 |
| M5 preview | invalid status jump -> 422 (`test_invalid_transition_is_422`) |
| Confirmation flow | `tests/test_confirmations.py` — 202 -> approve -> committed |

## 2. Against real Postgres (trigger tests)

The two trigger tests skip locally and run in CI. Locally:

```bash
docker compose up -d db
DATABASE_URL=postgresql+psycopg://plm:plm@localhost:5432/plm alembic upgrade head
TEST_DATABASE_URL=postgresql+psycopg://plm:plm@localhost:5432/plm_test pytest backend/tests
```

## 3. Manual smoke test

```bash
uvicorn app.main:app --port 8000
# Browser: http://localhost:8000/docs (Swagger UI)
```

Walk through:

1. `POST /api/v1/auth/login` with the bootstrap admin from `.env` -> copy token, click "Authorize"
2. `POST /api/v1/parts` **without** `direct=true` -> response is `202` + `confirmation_id` (nothing committed yet)
3. `GET /api/v1/parts` -> part is still missing
4. `POST /api/v1/confirmations/{id}/approve` -> part now exists as `P-000001`, revision `01`, status `draft`
5. Create the same name again -> `409 duplicate_part`
6. `POST /api/v1/parts/P-000001/revisions` -> revision `02`; then transition `draft -> review -> released` (needs approver role)
7. Add a BOM item to the `released` revision -> `409 released_immutable`
8. `GET /api/v1/admin/audit-log` -> every step has an entry with old/new + reason

## 4. PR review checklist (PR #1)

- [ ] CI green (ruff + alembic up/down on Postgres + 40 tests)
- [ ] `pytest` green locally
- [ ] Manual smoke test above completed
- [ ] No secrets committed (`.env` is gitignored; only `.env.example` is tracked)
