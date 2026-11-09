# ECR / ECO change management

## Concepts

- **ECR (Engineering Change Request)** — the request: "we should change X because ...".
  Status: `open -> in_review -> approved | rejected`.
- **ECO (Engineering Change Order)** — the concrete, approved implementation order,
  created from an approved ECR. It lists the affected part revisions
  (`POST /ecos/{number}/affected-revisions`). Status: `draft -> approved -> executed`.

## Rules

- Only **`released`** part revisions can be added as affected
  (`409 affected_not_released`). Draft/review/obsolete revisions are rejected.
- Affected revisions can only be changed while the ECO is `draft`
  (`409 eco_not_draft`).
- **`executed` (M9) really executes the change**: for every affected part revision a
  successor **draft** revision is created. Attributes and BOM are inherited from the
  affected revision; `change_reason` references ECO and ECR
  (`ECO-00001 (ECR-00001): <description>`). The transition response lists them under
  `created_revisions`. The affected `released` revision itself stays untouched
  (immutability). The new revisions are `draft` and go through the normal workflow
  (`draft -> review -> released`) — execution does not release them.
- Execution is **idempotent**: the workflow matrix has no `executed -> executed` row,
  a second attempt fails with `422 invalid_transition`.
- Everything (transition, execution, revision creation) writes `audit_log` entries
  (`transition`, `execute`, `part_revision/create`).
- The confirmation-token path (`?direct=false` -> `202` + confirmation -> approve)
  runs the exact same logic on approval, including revision creation.

## Status matrix (table `workflow_transitions`)

| entity | from | to | required role |
|---|---|---|---|
| ecr | open | in_review | editor |
| ecr | in_review | approved | approver |
| ecr | in_review | rejected | approver |
| eco | draft | approved | approver |
| eco | approved | executed | approver |

Status changes outside this matrix are rejected with `422 invalid_transition`;
roles are enforced via `required_role`.
