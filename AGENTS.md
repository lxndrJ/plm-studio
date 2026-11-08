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

## Next milestone (M5)

ECR/ECO endpoints (models + workflow matrix already in place); then report
engine (M6), AI layer (M7). M1-M4 are implemented incl. tests
(backend/tests, running on SQLite).
