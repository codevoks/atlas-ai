# Phase 9 — Bounded agentic research with LangGraph

## Scope

Implement one clearly defined deep-research workflow using LangGraph: plan bounded questions, retrieve Atlas evidence, optionally use a tightly scoped external research tool if product policy permits, synthesize a cited report, checkpoint state, expose progress/cancel/resume, enforce budgets/termination, and require human approval at sensitive boundaries.

## Engineering concepts

Agent versus workflow, planner/executor, typed tools, state and memory, checkpoints, retries, compensating behavior, termination, budgets, human-in-the-loop, tool provenance, agent evaluation, concurrency, when not to use agents, multi-agent patterns and coordination costs.

## Architecture changes and modules

Add research-run application module, LangGraph graph definition, typed state schema, planner node, retrieval/tool nodes, evidence accumulator, synthesis/validation node, approval node, checkpoint store, run scheduler/worker pool, and event/progress projection. Deterministic nodes remain ordinary services; LangGraph coordinates them.

## Data model changes

Add `research_runs`, `research_steps`, `tool_invocations`, `checkpoints`, `approvals`, and budget ledger/reservations. Persist workspace/actor/purpose, graph/config/model versions, input hash, states, attempts, timestamps, evidence/tool provenance, sanitized outputs, token/tool/cost usage, cancellation and terminal reason. Checkpoints are schema-versioned.

## APIs

Create/get/list/cancel/resume research runs; stream/poll safe progress events; submit/deny approval with optimistic concurrency and fresh auth; retrieve final report/evidence. Creation supports idempotency. Clients cannot submit arbitrary tool names, prompts, URLs, budgets, or graph state.

## Important interfaces

`ResearchGraph`; typed `ResearchState`; `Planner`; `ResearchTool.invoke(AuthorizedToolCall)`; `ToolPolicy`; `CheckpointStore`; `BudgetLedger.reserve/commit/release`; `ApprovalService`; `TerminationPolicy`; `ResearchEvaluator`. Tools receive minimum identity/scope and return sanitized bounded results.

## Security requirements

Allowlisted least-privilege tools; strict input/output schemas; SSRF/egress and redirect controls; tenant auth inside every retrieval/tool node; retrieved/web/tool content is untrusted; no arbitrary code/browser/shell; concurrent-safe budgets; maximum steps/tokens/tool calls/wall time/parallelism; approval for external/destructive/sensitive actions; safe checkpoint/log retention.

## Failure scenarios

Infinite loop; repeated plan; tool timeout/429/malformed/oversized output; checkpoint write conflict; crash after tool effect before record; cancellation race; budget oversubscription; approval becomes stale; prompt injection causes forbidden tool request; source changes mid-run; synthesis loses citations. Terminal reason is explicit and partial evidence remains inspectable.

## Testing strategy

Graph/node tests with deterministic models/tools; invariant/property tests for step and budget caps; checkpoint crash/resume at each edge; duplicate tool invocation/idempotency; cancellation/approval/revocation races; adversarial tool requests/SSRF; citation provenance; comparative evaluation against deterministic RAG; load/fairness of concurrent runs.

## Acceptance criteria

Every run terminates within hard bounds; restart resumes without unsafe duplicate effects; every claim/tool result is traceable; forbidden calls never execute; approvals are current and auditable; the research workflow beats or serves a named need beyond deterministic RAG with documented cost/quality; user can explain why it is an agent/workflow.

## Engineering review focus and implementation drills

Useful implementation drills: LangGraph node with typed state; termination policy; resumable checkpoint reducer; idempotent tool wrapper; budget race test; debug a looping planner. Design reviews compare supervisor, router, handoff, and parallel specialist patterns without implementing them.

## System-design review focus

Explain workflow versus agent, state/checkpoint consistency, side-effect idempotency, termination and budget enforcement, tool authorization, human approval, failure recovery, evaluation, and why multiple agents often worsen cost/reliability.

## Explicit deferrals

No general autonomous assistant, arbitrary web/code tools, long-term personal memory, or multi-agent runtime. Multi-agent is implemented only after a separate benchmark shows material improvement over this workflow and includes coordination/failure/evaluation design.
