# Phase 9 completion — bounded research workflow

Phase 9 adds a single bounded research workflow with persisted state, deterministic local tools, human approval, and cited report synthesis. The implementation proves the research workflow contract without requiring paid model APIs, hosted tools, cloud infrastructure, or a network-installed agent runtime package.

## Implemented scope

- Workspace-scoped `research_runs`, `research_steps`, `tool_invocations`, `checkpoints`, and `approvals` tables.
- A deterministic `ResearchGraph` boundary with planner, Atlas retrieval, local policy catalog, approval wait, and synthesis nodes.
- Fixed zero-cost graph/config/model versions and server-selected budgets.
- API endpoints for idempotent create, list, get, resume, cancel, and approval decision.
- Workspace UI for starting a bounded research run, inspecting step/tool/checkpoint provenance, approving or denying synthesis, and viewing the final cited report.
- Security controls for allowlisted tools, forbidden tool/URL/instruction requests, tenant-scoped retrieval, stale approval conflicts, idempotent tool records, bounded budgets, and zero paid-provider usage.

## Runtime behavior

The default workflow executes synchronously until it reaches the approval boundary:

```text
PENDING -> RUNNING -> WAITING_APPROVAL -> SUCCEEDED
```

Denied approvals terminate the run as `CANCELLED` with terminal reason `approval_denied`. User cancellation terminates nonterminal runs with `cancelled_by_user`. Resume is safe and idempotent for terminal and waiting-approval runs; persisted checkpoints retain the next node and evidence summary for recovery.

## Zero-cost path

The Phase 9 product gate uses:

- local PostgreSQL;
- deterministic development authentication;
- existing local filesystem object storage;
- existing Phase 8 hybrid retrieval;
- deterministic local planner/policy/tool/synthesis logic;
- no hosted model APIs;
- no external web calls;
- no cloud resources;
- no paid SaaS.

## LangGraph dependency decision

The Phase 9 specification calls for a LangGraph-style bounded graph. LangGraph is not present in the current local dependency set, and adding a network-installed runtime dependency would make the product gate depend on package availability outside the repository. The implementation therefore keeps the graph behind a narrow `ResearchGraph` boundary and ships a deterministic local runner that proves the API, persistence, checkpoint, tool-policy, approval, and budget contracts. A LangGraph adapter remains a later evidence-gated swap behind the same boundary.

## Validation evidence

- Migration `0008_phase8 -> 0009_phase9` succeeded.
- Focused Phase 9 API tests passed: `2 passed`.
- Full API tests passed: `42 passed`.
- Worker tests passed: `4 passed`.
- Web tests passed: `1 passed`.
- Full lint passed across all packages.
- Full typecheck passed across all packages.
- Full production build passed across all packages.

## Security and failure evidence

- Forbidden prompt/tool/SSRF-like request returns validation failure before run persistence.
- Cross-tenant research-run read returns non-disclosing `404`.
- Duplicate create with the same idempotency key returns the same run without duplicate tool records.
- Stale cancellation version returns `409`.
- Denied approval terminates the run as cancelled.
- Reusing a decided approval returns `409`.
- Approved synthesis creates a cited report only after current approval.
- Tool invocations record stable idempotency keys and sanitized summaries.
- Usage remains zero-cost with `paid_services=false`.

## Deferred

- General autonomous assistant behavior.
- Arbitrary web, browser, shell, code, or connector tools.
- External research providers and egress policy.
- LangGraph runtime adapter in the default dependency set.
- Multi-agent research runtime.
- Hosted model/tool providers and billable approval flows.
- Streaming progress/event delivery.
