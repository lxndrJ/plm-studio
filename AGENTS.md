# AGENTS.md - Rules for Vibe Code in this repo

Project: PLM Studio (in-house PLM with AI prompt layer).
Stack: FastAPI (Python 3.12) + PostgreSQL 16 + Alembic + SvelteKit.
Blueprint and milestones M0-M7: see README.md and docs/.

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

## Next milestone (M7)

AI layer (LiteLLM, tools generated from /openapi.json, guardrails).
M1-M6 are implemented incl. tests (backend/tests, running on SQLite).
M6 added the report engine (app/api/reports.py, app/services/report_service.py):
PDF via Typst (TYPST_BINARY), frozen content_snapshot per report, released-only
content, internal attribute keys (preis/lieferant/...) stripped.
