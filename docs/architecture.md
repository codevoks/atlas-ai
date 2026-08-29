# Atlas AI architecture

For a diagram-first walkthrough of the system boundary, ingestion state machine, retrieval/RAG flow, immutable lineage, and evidence-driven scaling path, see `docs/system-design-visuals.md`.

## Purpose and requirements

Atlas AI is a multi-tenant SaaS for securely ingesting enterprise sources, retrieving tenant-authorized evidence, answering questions with verifiable citations, and running bounded deep-research workflows. The initial product supports workspaces, membership/RBAC, uploaded documents, asynchronous ingestion, hybrid search, grounded answers, evaluations, and auditable research runs.

The architecture optimizes first for correctness, explainability, tenant isolation, debuggability, and a clean path to measured scale—not for hypothetical internet scale. Example capacities belong in load-model scenarios, not product claims.

Core non-functional requirements:

- Tenant isolation and authorization are correctness properties.
- Accepted uploads and job state are durable; asynchronous work is at-least-once and idempotent.
- Search is available only over successfully published document versions and is eventually consistent with uploads.
- Workspace metadata mutations require strong transactional consistency.
- Answers must expose evidence identity and citation validation status.
- All network calls have timeouts; retries are bounded and limited to classified transient failures.
- Telemetry must correlate user request, job, retrieval, model call, and research run without leaking document content or secrets.
- Cost, latency, and quality are measured per important AI operation.
- The repository must remain buildable, testable, and demonstrable at zero monetary cost. Paid cloud, SaaS, domains, and model APIs are optional integrations only and are disabled by default.

## System context and trust boundaries

```text
Browser (untrusted)
   | HTTPS/session
Next.js web/BFF ---------------- identity provider
   | service-authenticated HTTPS
FastAPI control/query plane
   |---- PostgreSQL (authoritative metadata and exact vector baseline)
   |---- Object storage (immutable source artifacts)
   |---- Redis (queue/cache/rate coordination; non-authoritative)
   |---- Model/embedding/reranking provider adapters
   `---- Durable job publication
                  |
              Worker fleet
                  |---- parsers/sandboxed conversion boundary
                  |---- object storage / PostgreSQL / Redis
                  `---- deterministic local fakes by default; external AI providers only when explicitly enabled

Later, only if evidence justifies it:
FastAPI/worker ---- OpenSearch (derived lexical/vector search projection)
```

Trust boundaries exist at the browser, service ingress, tenant authorization layer, uploaded-file parser, retrieved-content boundary, external model/tool provider, object store, job transport, and observability export. Content crossing a boundary is data, never authority.

## Major components and responsibilities

| Component | Owns | Must not own |
|---|---|---|
| `apps/web` | Product UI, session UX, server-side BFF calls, safe rendering | Domain authorization, direct database/provider access |
| `apps/api` | Auth context, use cases, REST contracts, transactions, search/RAG orchestration | Long-running parsing/embedding, provider-specific logic in routes |
| `apps/worker` | Durable job consumption, ingestion/reindex/research steps, heartbeats/retries | Browser concerns, bypassing domain authorization rules |
| PostgreSQL | Tenants, memberships, sources, document versions, jobs, chunks, embedding sets, exact vector baseline, evaluations, runs, audit references | Large source blobs, ephemeral locks as the only correctness mechanism |
| Object storage | Immutable uploaded/raw/derived artifacts with tenant-prefixed keys | Authorization decisions, mutable job state |
| Redis | Broker/queue coordination, cache, distributed rate/budget primitives | System of record |
| Provider adapters | Typed embedding/generation/reranking/tool interfaces, deterministic local fakes for tests/demos, timeout/error normalization | Business policy, direct paid external calls by default |
| Retrieval subsystem | Candidate generation, filters, fusion, reranking, evidence/context assembly | Authorization bypass, free-form provider output |
| Evaluation subsystem | Versioned datasets/runs/metrics/comparisons | Production decisions without reviewed thresholds |
| Observability | Structured events, traces, metrics, cost/latency attribution | Raw sensitive document/prompt logging by default |

Logical code boundaries inside API/worker are `domain`, `application`, `infrastructure`, `retrieval`, `ai`, `api`, and worker entrypoints. Imports point inward: domain has no framework/provider dependencies; application depends on ports; infrastructure implements ports; routes and job consumers adapt external input.

## Current implemented baseline after Phase 11

The repository currently implements the control-plane foundation plus the storage, ingestion, parsing, normalization, chunking, embedding, lexical retrieval, semantic retrieval, hybrid-evidence retrieval, deterministic grounded answer, citation-integrity, offline evaluation, evidence-gated query expansion, bounded research workflow, security guardrail slice, and production-hardening baseline: `apps/web`, `apps/api`, `apps/worker`, `packages/config`, and `packages/shared-types`. The API owns identity resolution, workspace use cases, RBAC policy, SQLAlchemy persistence, Alembic migrations, audit events, source/document/upload/chunk/search/answer/evaluation/research/security/operations contracts, signed local upload handling, semantic retrieval, PostgreSQL lexical retrieval, deterministic RRF hybrid fusion, retrieval diagnostics, bounded retrieval planning, deterministic query expansion, transformed-query provenance, context construction, deterministic generation, citation validation, answer-run persistence, evaluation-run persistence, deterministic metric computation, baseline/candidate ablations, baseline approval, bounded research run orchestration, tool policy, budget enforcement, checkpoint persistence, approval-gated synthesis, deterministic input/output guardrails, fixed-window quota enforcement, redacted security-event persistence, local no-content telemetry, admin operational posture visibility, protected internal metrics, and OpenAPI export. The web app owns local sign-in UX, server-side BFF calls, workspace/member/source/document screens, direct-upload orchestration, chunk preview display, semantic/lexical/hybrid evidence search UI, retrieval-config selection, retrieval-plan visibility, grounded-answer UI, latest evaluation-run visibility, bounded-research run visibility, approval controls, report display, security posture/event visibility, operations posture visibility, Tailwind CSS styling, and security headers. The worker owns deterministic ingestion-job claiming, lease/version checks, object integrity verification, text/Markdown parsing, canonical normalization, deterministic chunking, deterministic local embedding batches, derived artifact writes, and atomic chunk/embedding publication.

The implemented persistent tables are `users`, `workspaces`, `memberships`, `audit_events`, `idempotency_records`, `sources`, `upload_intents`, `documents`, `document_versions`, `ingestion_jobs`, `job_events`, `chunks`, `embedding_sets`, `chunk_embeddings`, `answer_runs`, `answer_evidence`, `citations`, `evaluation_datasets`, `evaluation_dataset_versions`, `evaluation_cases`, `evaluation_runs`, `evaluation_results`, `evaluation_baselines`, `research_runs`, `research_steps`, `tool_invocations`, `checkpoints`, `approvals`, `security_policy_configs`, `security_events`, `quota_counters`, `content_trust_records`, and `retention_tombstones`. Phase 8 extended `answer_evidence` with JSON retrieval provenance and `evaluation_cases` with an explicit retrieval configuration version. Phase 9 adds workspace-scoped research state, checkpoints, tool invocation records, approval decisions, budgets, usage, terminal reasons, and cited report output. Phase 10 adds security posture/event visibility, deterministic guardrail metadata, atomic quota counters, content-trust/quarantine metadata, and retention tombstone foundations. The `chunks` table has a PostgreSQL full-text GIN expression index for the English lexical baseline. Local development uses a filesystem-backed object-store adapter with tenant-prefixed keys, HMAC-signed upload URLs, immutable uploaded objects, and normalized derived artifacts; production object storage remains behind the same adapter boundary.

Phase 11 intentionally supports a small text-first parser surface, deterministic local hash embeddings, PostgreSQL full-text lexical retrieval, exact cosine semantic retrieval, deterministic RRF hybrid fusion, deterministic local reranking, budgeted context construction, deterministic local answer generation, citation validation against supplied evidence spans, versioned evaluation datasets, immutable labeled cases, synchronous deterministic local evaluation runs, metric-version provenance, aggregate/slice/failure reports, append-only baseline approval, one evidence-gated advanced RAG configuration (`phase8-multi-query-expansion-v1`), one bounded research workflow, one deterministic security guardrail suite, and one local production-hardening suite. The research workflow uses a deterministic graph boundary with planner, Atlas retrieval tool, local policy-catalog tool, checkpoint, approval, and synthesis nodes. Guardrails scan high-risk inputs and outputs for indirect prompt injection, secret-like values, SSRF-like content, and unsafe generated output; enforce local fixed-window quotas for search, answer, and research operations; record redacted security events; and expose admin-only security posture/events in the workspace UI. Phase 11 telemetry records route templates, request/trace IDs, statuses, and latency summaries only; content capture is disabled by default and hosted export is not required. Operations posture exposes SLO objectives, observed local route metrics, dependency status, capacity bottleneck watchlists, zero-cost cost posture, and runbook summaries. Unsupported, binary, PDF, archive, and invalid-UTF-8 files fail safely without publishing chunks or embeddings. Answers and research reports are grounded only in retrieved workspace evidence; fabricated or absent citations are not represented as verified. Evaluation labels are used only after the system-under-test has produced retrieval and answer outputs; hidden expected answers are never passed into retrieval or generation. Malware scanning, PDF/office/OCR extraction, Redis-backed coordination, external object-storage credentials, hosted embedding/generation/reranking/judge providers, hosted telemetry, contextual chunk projections, ANN vector indexes, OpenSearch, streaming, online experimentation, external research tools, enterprise DLP/KMS/HSM, compliance certification, external penetration testing, live AWS provisioning, and multi-agent runtime remain deferred behind explicit evidence and opt-in approval. The Phase 11 build/test/demo path is zero-cost: local PostgreSQL, local filesystem object storage, deterministic development authentication, deterministic parser/chunker/embedding/retrieval/generation/evaluation/query-expansion/research/security logic, PostgreSQL full-text search, exact cosine retrieval over stored normalized vectors, deterministic RRF fusion, verified citations, deterministic metrics, approval-gated report synthesis, local quota counters, redacted security events, local no-export telemetry, plan-only Terraform baseline, local CI/container validation artifacts, and no model-provider or cloud API calls.

## Canonical data model

All tenant-owned tables include `workspace_id`, even when derivable, to make filtering, constraints, partitioning, auditing, and row-level defense possible. IDs are opaque UUIDs. Timestamps are UTC. Mutable records use optimistic versioning where concurrent edits matter.

- `users`: identity-provider subject and profile metadata.
- `workspaces`: tenant lifecycle and policy configuration.
- `memberships`: `(workspace_id, user_id)`, role, status; unique membership.
- `sources`: logical origin and source type; no secret values in ordinary columns.
- `documents`: stable logical document within a source/workspace.
- `document_versions`: immutable content version, object key, digest, media type, size, ingest status, parser/chunker provenance, normalized artifact pointer/digest, aggregate counts, embedding-set coverage, active/publication state.
- `ingestion_jobs`: durable state machine, attempt count, idempotency key, lease/heartbeat, error class, progress, requested configuration.
- `chunks`: immutable chunk identity tied to document version; ordinal/page/span, text or protected text reference, token count, metadata, content hash, chunker version.
- `embedding_sets`: workspace-scoped provider/model/version/dimension/normalization/configuration and lifecycle for migrations.
- `chunk_embeddings`: `(chunk_id, embedding_set_id)`, normalized vector, status, token count; coexistence enables model migration.
- `search_queries`: optional redacted/debuggable query execution metadata with retention controls; Phase 5 does not persist user queries by default.
- `answer_runs`: query, model/config versions, status, token/cost/latency, policy outcome.
- `answer_evidence`: ordered immutable references to chunk versions, retrieval scores/stages, quoted span.
- `citations`: answer span/claim to evidence reference plus validation outcome.
- `evaluation_datasets`, `evaluation_cases`, `evaluation_runs`, `evaluation_results`: versioned offline evaluation lineage.
- `research_runs`, `research_steps`, `tool_invocations`, `checkpoints`: bounded workflow state, budgets, approvals, provenance.
- `audit_events`: actor, workspace, action, target, outcome, trace ID, safe metadata.

Database invariants include composite tenant-aware foreign keys where practical, uniqueness for idempotency keys, immutable version content, only one active published version per document, and no searchable chunks until a version atomically transitions to `READY`.

## Core flows

### Upload and ingestion

1. API authorizes `document:create`, validates declared file constraints, and creates an upload intent with a tenant-scoped object key.
2. Client uploads via short-lived signed URL. API finalizes by verifying object metadata/digest and creates the document version plus durable job in one transaction.
3. Finalization creates the document, immutable document version, ingestion job, job event, audit event, and idempotency record in one PostgreSQL transaction.
4. The worker claims jobs with `FOR UPDATE SKIP LOCKED`, a lease owner, heartbeat timestamp, attempt counters, expected version, and bounded retry states.
5. Worker execution verifies stored object size/digest, rejects unsupported or unsafe file classes, parses supported text/Markdown input, normalizes text, writes a normalized derived artifact, creates deterministic chunks, embeds chunks against the active embedding set, and atomically publishes the document version as ready with chunk/provenance/embedding metadata.
6. Cancellation is cooperative. Dead-letter state preserves diagnosable error metadata and a safe replay path.

### Search

1. API derives workspace/user authorization context; it never accepts workspace authority from the request alone.
2. Validate query, filters, limits, rate/cost budget, and visibility policy.
3. Semantic retrieval embeds the query with the configured deterministic provider, loads only authorized `READY` active version embeddings inside the tenant/status filter path, ranks candidates with exact cosine similarity, and returns typed evidence.
4. Lexical retrieval executes PostgreSQL full-text search over authorized `READY` active chunks with the same tenant/status/filter predicates and returns typed evidence.
5. Hybrid retrieval obtains semantic and lexical candidates under the same authorization policy, deduplicates by `(chunk_id, document_version_id)`, applies deterministic Reciprocal Rank Fusion, and returns typed evidence plus redacted stage diagnostics when requested.
6. Cache only with workspace, authorization fingerprint, index/version/config, and normalized-query keys; default to no cross-user cache until proven safe.

### Grounded answer

Search produces immutable evidence. Phase 6 context construction deduplicates, applies bounded evidence counts and total character budgets, and labels untrusted excerpts. The deterministic local generation adapter receives typed evidence only and has no provider/network side effects. Post-processing checks cited evidence ranks, marker spans, and quoted text against supplied evidence, persists answer runs plus immutable answer evidence and citations, and returns either a grounded answer with verified citation status or a safe no-evidence refusal—never invented citations.

### Bounded research

A LangGraph workflow is used only after deterministic RAG is measured. Run state and checkpoints are durable. Each tool has a schema, allowlist, authorization scope, timeout, cost, and output sanitizer. The loop has maximum steps/tokens/cost/wall time, explicit terminal states, and approval nodes for sensitive actions. Atlas begins with one orchestrated agent/workflow; multi-agent runtime patterns remain deferred unless benchmarks justify their coordination and evaluation cost.

## API boundaries

Version public contracts under `/v1`. JSON uses stable error envelopes (`code`, `message`, `request_id`, safe `details`). Long work returns `202` plus a status resource. Pagination is cursor-based. Commands support an `Idempotency-Key` where replay is plausible.

Primary resource groups:

- `/v1/workspaces`, `/members`, `/roles` — tenancy and RBAC.
- `/v1/sources`, `/documents`, `/document-versions`, `/uploads` — source lifecycle.
- `/v1/ingestion-jobs/{id}` and cancellation/retry commands — asynchronous status.
- `/v1/workspaces/{workspace_id}/search` and `/search/semantic` — typed evidence and bounded debug metadata.
- `/v1/workspaces/{workspace_id}/answers` and `/answer-runs/{id}` — synchronous deterministic grounded answer and stored run retrieval.
- `/v1/evaluation-datasets`, `/evaluation-runs` — admin/developer workflows.
- `/v1/research-runs`, `/steps`, `/approvals` — bounded workflow control.

Formal schemas live in Python/Pydantic; an OpenAPI artifact is the language-neutral contract. TypeScript types are generated or contract-tested, not manually duplicated. Internal provider/job interfaces are documented in `docs/decisions.md` and phase specifications.

## Consistency, availability, and recovery

- Strong: membership/role changes, upload finalization metadata, active document-version publication, budget reservation, idempotency registration, approvals.
- Eventual: upload-to-search visibility, cache invalidation, derived search projections, observability export, aggregate analytics.
- Read-your-writes: metadata should be immediate; ingestion status is polled/streamed from the authoritative job record; search visibility begins only after publication.
- Failure isolation: provider outage does not corrupt state; one poisoned document does not stall a queue; Redis loss causes degraded coordination/rebuild, not data loss; derived indexes are rebuildable.
- Backups: PostgreSQL point-in-time recovery and object versioning/lifecycle are production requirements; restore drills and reindex procedures are part of hardening.

## Scaling model

Capacity planning starts from named variables rather than invented facts:

- `W`: active workspaces; `U`: active users; `D`: documents; `B`: average bytes/document.
- `C = D × chunks/document`; `E = C × dimensions × bytes/component × index overhead`.
- `Q`: search QPS; candidate work is approximately `Q × candidate_k × retrieval branches`.
- `A`: answers/second; model tokens/day = input context + query/instructions + output across all runs and retries.
- Ingestion demand = uploaded bytes/time, documents/time, parse CPU, chunks/time, embeddings/time; queue arrival rate must remain below sustainable service rate or backlog age grows.
- Research load = concurrent runs × maximum steps × tool/model demand, constrained by budgets.

Track p50/p95/p99 latency, error rate, saturation, queue depth/oldest age, chunks/sec, provider throttling, index size/recall, tokens/cost per successful answer, and evaluation quality. Likely first bottlenecks are external-model quota/latency, parsing CPU/memory, vector-index recall/latency, PostgreSQL I/O, and unbounded context—not the web tier.

At 100×, first separate worker pools and quotas by workload/tenant, add replicas/partitioning and connection controls, batch embeddings, and move derived search to OpenSearch only if measured PostgreSQL limits or search-feature needs justify operational cost. At 10M documents, evaluate sharding/partitioning by tenant, dedicated large-tenant placement, asynchronous index projections, and reindex backfills; do not promise a single topology for every tenant distribution.

## Observability and cost

OpenTelemetry provides vendor-neutral traces/metrics/log correlation with local/no-export defaults. An AI trace sink such as Langfuse may capture redacted AI traces, evaluation metadata, prompt/model/config lineage, latency, tokens, and cost when explicitly configured. Stable IDs connect HTTP requests, jobs, document versions, retrievals, answer runs, and research steps. Content capture is off by default and governed by tenant policy and retention.

Phase 11 implements the first local telemetry boundary. API middleware emits a trace ID and records bounded in-memory metrics keyed by route template, method, status, and duration. Admin operations posture and protected internal metrics expose safe aggregates only. Telemetry failure is non-authoritative and must not block product correctness. Hosted exporters, dashboards, alert routing, and long-retention telemetry stores remain optional deployment work.

Dominant production cost drivers are model tokens, embeddings/re-embeddings, reranking, parser compute, vector/search storage, object storage/egress, database I/O, and trace retention. Local tests and demos use deterministic fakes or local open-source services so cost instrumentation can be validated without monetary spend. Quality changes require latency/cost/quality evaluation, not intuition alone.

## Evolution rule

PostgreSQL/pgvector, Redis, S3-compatible storage, and provider adapters are starting decisions, not permanent dogma. Architecture changes require evidence, an ADR entry, migration/rollback design, evaluation comparison, and an explanation the owner can defend. See `docs/decisions.md`, `docs/threat-model.md`, and the preserved engineering history under `docs/internal/engineering-history/`.
