# ADR 0001: Tech stack for the in-house PLM

Status: accepted (2026-11-08)

## Context

Small team, self-hosted on a VPS (Raspberry Pi as a test option), AI prompt
layer as the primary interface, internal file management for vector/JPEG,
and report generation for external parties.

## Decision

PostgreSQL 16 as the database, FastAPI (Python 3.12) as the backend,
LiteLLM as the OpenAI-compatible model proxy, SvelteKit as the frontend,
Docker Compose as deployment, Typst for reports.

## Rationale

- PostgreSQL: relational integrity for part/BOM references, recursive CTEs
  for where-used, JSONB for flexible attributes.
- FastAPI: automatically generates an OpenAPI schema. This schema is later
  literally the tool contract of the AI agent, so there is no second,
  divergent tool description.
- LiteLLM: models (Mistral/DeepSeek/local) interchangeable without code
  changes, cost control centralized.
- Typst: PDF generation without headless Chrome, runs on ARM.

## Alternatives (rejected)

- Wrapper around Aras/OpenPLM: an agent layer on top of the core means the
  data integrity rules (immutability, workflow) depend on the external
  system; unnecessary operational overhead for a small team. Deliberately
  chose full in-house build.
- Node/NestJS backend: equally capable, but the Python ecosystem for
  CAD/materials (OCC, stepler, pandas) fits a PLM environment better.
- MongoDB: referential integrity (no BOM line without a valid part
  reference) is a core requirement; a relational DB enforces it.
- Keycloak: overkill for a small team; JWT is enough.

## Consequences

- All business rules must be implemented and tested ourselves
  (migration mandatory for every rule).
- The OpenAPI schema is part of the public contract: breaking changes need
  a new API version.
