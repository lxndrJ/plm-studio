# PLM Studio AI agent

The agent (`agent/` service, port 8001) is a thin LLM chat layer on top of the
PLM REST API. Its tool functions are **generated from the API's
`/openapi.json`** (`agent/plm_agent/toolgen.py`) — the agent can only call
documented endpoints, never invent its own.

- UI: `/agent` page in the frontend (SSE chat, quick-action buttons, inline
  approval of proposals). Direct API: `POST /chat` on the agent service.
- System prompt / behaviour rules: [../agent/plm_agent/system_prompt.md](../agent/plm_agent/system_prompt.md)
- API-wide contract (also enforced by the backend): [api-contract.md](api-contract.md)

## What the agent can do

**Read (directly, no confirmation needed):**

- Search and inspect parts (`GET /parts`, `GET /parts/{pn}`) incl. revisions
  and typed attributes
- BOM of a part/revision, where-used analysis, BOM diff between two revisions
- Documents and their files/revisions, ECR/ECO lists and details,
  pending confirmations, reports
- Admin reads (role `admin`): audit log, stats, users, part classes, service logs

**Write (always as a *proposal*, never executed by the agent itself):**

- Create parts / new revisions (part numbers come **only** from the number
  range), update draft attributes, add BOM positions
- Create ECRs/ECOs, add affected revisions, propose status transitions
- Create documents, upload files, generate reports (BOM / ECR, PDF)
- Every mutating call without `direct=true` returns `202` + a confirmation
  token; the user approves/rejects it in the UI (chat bubble or
  `/confirmations` page). The agent never approves its own proposals.

## Rules the agent follows

1. Read state first (GET), then change, then verify (GET again).
2. Duplicate search before every create; on `409` show the hits and ask.
3. Never modify `released` revisions — changes go through new revisions with
   a `change_reason`.
4. Status changes only via the transition endpoints (workflow matrix).
5. Part numbers are assigned only by the system, never proposed manually.
6. Every write carries a reason (audit trail).
7. On `429`/5xx: exponential backoff, max 3 attempts, then inform the user.
8. External reports contain released content only; cost/supplier data never
   leaves the internal system.

## Service token

If `AGENT_SERVICE_TOKEN` is set, agent-service endpoints (`/chat`,
`/conversations*`, `/logs`) require the header `X-Agent-Token`. The frontend
dev/preview proxy injects it server-side for `/agent-api/*` (see
`frontend/vite.config.ts`), so the browser never needs the token.
