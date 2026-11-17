# ADR 0003: AWS-native target architecture

Date: 2025-05-30
Status: proposed

## Context

The current deployment (docker-compose) runs five self-managed services
(api, previews worker, agent, litellm proxy, frontend proxy) plus Postgres
and a shared file volume. The goal is to move to AWS while taking maximum
advantage of managed AWS services: replace self-operated infrastructure
with AWS primitives, reduce the number of own services, and use IAM-based
auth instead of static keys where possible.

Constraints from the existing system (must not be weakened):

- Released revisions are immutable via a DB trigger; status transitions only
  via the workflow matrix (real PostgreSQL required, incl. recursive CTEs).
  Schema changes only via Alembic migrations.
  Every write produces an audit_log entry; writes go through the
  confirmation-token guardrail.
- Original document files are immutable; previews are generated from them.
- The agent never performs direct writes and never self-approves proposals;
  these guardrails stay in our own runner code.

## Decision

AWS-native hybrid: Lambda for the stateless HTTP core, containers (Fargate)
only where Lambda is a poor fit (long-running conversion, SSE streaming),
and managed AWS services for everything stateful.

### Service mapping

| Today (compose) | AWS target | Rationale |
|---|---|---|
| api (uvicorn :8000) | AWS Lambda + Lambda Web Adapter behind API Gateway HTTP API | Stateless FastAPI; API Gateway adds auth/rate limiting; Lambda scales with usage. Aurora + RDS Proxy absorbs connection churn. |
| db (postgres:16) | Aurora Serverless v2 (PostgreSQL) + RDS Proxy | Real Postgres keeps trigger, recursive CTEs, JSONB attributes; serverless scaling for business-hours load; secrets via Secrets Manager. |
| migrate (alembic one-shot) | CI step (GitHub Actions) running `alembic upgrade head` against Aurora | Migrations run as a controlled pipeline step, not at container start. |
| previews worker + `preview_jobs` polling | SQS queue + Fargate service (or AWS Batch for large jobs) | Typst binary and conversion time exceed the Lambda profile (image size, 15-min limit is fine but 1-GB tmp and packaging make it awkward); SQS replaces DB polling, gives DLQ and visibility timeouts. |
| filedata volume (`STORAGE_DIR`) | S3 (one bucket, originals under a protected prefix with Object Lock / versioning) | Replaces the shared volume; S3 Versioning preserves the originals-immutability property; presigned URLs for upload/download offload the API. |
| agent (:8001, SSE) | Fargate service behind ALB (SSE) | Streaming responses from Lambda are possible but awkward; Fargate keeps the SSE loop simple and holds no state anyway (conversations live in Postgres). |
| litellm proxy | Amazon Bedrock via boto3 `converse` / `converse_stream` in the runner | Removes an entire self-operated service; IAM role instead of LITELLM_MASTER_KEY/OPENAI_API_KEY; Mistral and Anthropic models available; AWS Bedrock Guardrails as an extra layer on top of our own agent guardrails. |
| frontend (SvelteKit proxy server) | Static build to S3 + CloudFront; token-injecting proxy endpoints moved into a small Lambda (Function URL) | The UI itself is static; only the server-side proxy (AGENT_SERVICE_TOKEN injection) needs compute. |
| in-memory log ringbuffers | CloudWatch Logs (service logs) | Ringbuffers do not survive Lambda cold starts; `/logs` page reads via CloudWatch Logs Insights API instead. |

### Auth & security mapping

- JWT stays for API auth; JWT_SECRET in Secrets Manager.
- LLM access: IAM role on the agent task with `bedrock:InvokeModel` for the
  specific model ARNs (least privilege, no static API keys).
- S3 access: task/lambda roles scoped to the bucket prefixes; presigned URLs
  for browser uploads/downloads.
- DB credentials: Secrets Manager + RDS Proxy.
- Login rate limiting stays in-app (429 + Retry-After) and is additionally
  covered by API Gateway throttling.

## Consequences

- Two services disappear entirely (litellm proxy, shared file volume);
  one new managed queue (SQS) and one storage primitive (S3) are introduced.
- Required refactors, in order:
  1. Storage abstraction: replace `STORAGE_DIR` filesystem access with an
     S3-backed storage service (upload/download, preview job payloads).
  2. Preview pipeline: enqueue to SQS instead of inserting `preview_jobs`
     rows and polling; worker consumes SQS messages and keeps job state in
     the DB for observability.
  3. Agent runner: switch from OpenAI-compatible chat completions to Bedrock
     `converse_stream` (toolUse blocks); tests move from httpx MockTransport
     to a boto3 stub.
  4. Logs: replace ringbuffer endpoints with CloudWatch Insights queries
     (admin-only, as today).
  5. IaC: CDK or Terraform for Lambda, Fargate, Aurora, SQS, S3, CloudFront.
- Cost profile: Lambda + Aurora Serverless scales down outside business
  hours; the always-on remainder is the Fargate agent/preview pair, which is
  small compared to the removed litellm + proxy servers.
- Rollout can be incremental: storage → S3 and previews → SQS also work in
  the current compose setup, so each step is testable before touching
  Lambda/Fargate.

## Alternatives considered

- Full serverless (everything on Lambda): rejected — SSE streaming from the
  agent and the Typst preview worker are poor Lambda fits.
- ECS Fargate for all services (no Lambda): simpler, but leaves the API
  always-on and forgoes the business-hours cost profile; also fine as a
  stepping stone.
- Bedrock Agents / AgentCore instead of our ReAct runner: rejected — the
  write guardrails (no direct writes, never self-approve) must stay in
  auditable code we control.
