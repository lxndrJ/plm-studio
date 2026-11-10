# Phase 3 plan (M12+)

Phase 1 (M1-M7) and Phase 2 (M8-M11) are implemented — see the status list
in [README.md](../README.md). Phase 3 therefore starts at **M12**.

The full blueprint lives in the external project document "PLM-System
Blueprint"; this plan is derived from the repository state.

## Proposed milestones

| Milestone | Topic | Rationale (repo evidence) |
|---|---|---|
| M12 | CAD/STEP integration: STEP upload, CAD thumbnails, 3D preview in the frontend, CAD document <-> part links | README promises CAD documents, ADR 0001 names OCC/stepler; the preview worker only covers JPG/PNG/SVG/PDF/AI/EPS/PSD |
| M13 | Notifications & webhooks: e-mail/webhook on workflow events (new confirmation, ECR `in_review`, ECO `executed`) | Workflow events land in the audit log; the only proactive signal today is the confirmations badge (30 s poll) |
| M14 | Search & BOM-diff report: full-text search (Postgres FTS) over parts/documents + BOM comparison report via the Typst engine | M11 already added BOM-explosion/ECR reports and CSV/JSON export; the BOM diff exists as API but not as report; part search has no FTS index |
| M15 | Import & batch: CSV/XLSX import for parts + BOMs, bulk changes via ECO | Export exists since M11 (`/export/*`), but the seeder only creates TEST data — there is no import path for real data |
| M16 | Agent hardening: scheduled/triggered runs (Mistral Workflows), evaluations of the agent loop, RAG over the document corpus | The agent (M7/M10/M11) is a service with chat UI but so far interactive only (one prompt = one run) |

## Optional backlog (after M16)

- SSO/OIDC instead of JWT-only auth
- API v2 (ADR 0001: breaking changes require a new API version)
- Multi-tenancy
- Performance: caching, read replica

## Working rules for Phase 3

Unchanged from [AGENTS.md](../AGENTS.md): TDD for business rules, schema
changes only via Alembic migrations, Conventional Commits, ruff + pytest
green before every commit. PLM data rules apply as before: released
revisions immutable, writes only via confirmation tokens, every write
audited, part numbers only from the number-range generator.
