# API contract for the AI agent

These rules apply to every client of the PLM API, especially the AI agent.
The backend enforces them technically; the agent follows them additionally
(defense in depth).

1. Use only documented endpoints and field names. The OpenAPI schema at
   /openapi.json is the single source of truth.
2. Validate required fields before sending write calls.
3. Writes run as proposed writes with a confirmation token: 202 back,
   the user confirms, only then execute.
4. Always GET (current state) first, then mutate, then GET (verify).
5. Multi-step changes (part + BOM + document) in one transaction or one
   batch, if the endpoint offers it.
6. Rate limits and error codes: on 429/5xx use exponential backoff,
   max 3 attempts, then report to the user.
7. Part numbers are assigned ONLY by the number-range generator, never
   suggested or set manually by the agent.
8. Duplicate check before every create: show search hits to the user;
   409 is a stop signal, not a bypass signal.
9. Released revisions are immutable; changes always go through new
   revisions with change_reason.
10. Status transitions only via the transition endpoints; the allowed
    matrix lives in the workflow_transitions DB table.
11. Every write call carries a reason (audit trail).
12. Internal data (costs, suppliers) is never put into external reports by
    the agent; the report filter only allows released content.
