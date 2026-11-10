# AGENTS.md - Rules for Vibe Code in this repo

Project: PLM Studio (in-house PLM with AI prompt layer).
Stack: FastAPI (Python 3.12) + PostgreSQL 16 + Alembic + SvelteKit.
Blueprint and milestones M0-M11: see README.md and docs/. Phase 3 plan (M12+): docs/phase-3.md.

## Working style

- TDD for business rules: write the test first (tests/), then the
  implementation. Acceptance criteria per milestone are in the README.
- Every schema change only via a new Alembic migration (alembic revision),
  never by hand in the DB.
- Conventional Commits, small reviewable changes.
- Ruff (line-length 100) and pytest must be green before every commit.

## PLM data rules (critical, never violate)

1. Part numbers are assigned exclusively by the number-range generator
   (app/services/numbering.py). Never set numbers client-side.
2. Released revisions (status=released) are immutable; a DB trigger enforces
   it. Changes always go through new revisions with change_reason.
3. Status transitions only via the matrix in workflow_transitions;
   never UPDATE a status directly.
4. Every write creates an audit_log entry (who/what/why/old/new).
5. No part without classification, no BOM line without a valid part
   reference, no DELETE on released objects.
6. Write API operations are proposed writes with a confirmation token
   (see app/guardrails/confirmations.py).
7. Technical attributes are revision-scoped: they live on part_revisions
   (JSONB) and are inherited by successor revisions. parts carries only
   neutral fields. Attribute values are validated against the typed
   definitions in class_attributes (see docs/adr/0002-data-foundation.md).
8. BOM units must exist in the units master data (units table); unknown
   units are rejected with 422 unknown_unit.
9. Part classes form a tree via part_classes.parent_id. Class filters in
   search include the whole subtree; unknown class codes are 404.

## Milestones

Phase 1 (M0-M7) is implemented incl. tests (backend/tests on SQLite,
agent/tests with mocked LLM/API). M7 added the AI agent (agent/plm_agent):
toolgen maps /openapi.json to function-calling tools (writes without
`direct`, no auth/approve/admin endpoints), the runner loops via LiteLLM and
reports 202 proposals back instead of self-approving.

Phase 2 (M8-M11) is implemented incl. tests: M8 security/user management,
M9 ECO execution, M10 agent service (SSE chat API + conversation persistence,
compose service :8001), M11 UI/reports/export (chat + admin pages, typed
attribute forms, CSV/JSON export, BOM-explosion + ECR report templates).
Phase 3 (M12+) is planned in docs/phase-3.md.
