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

## System context and trust boundaries

```text
Browser (untrusted)
   | HTTPS/session
Next.js web/BFF ---------------- identity provider
   | service-authenticated HTTPS
FastAPI control/query plane
   |---- PostgreSQL + pgvector (authoritative metadata/index initially)
   |---- Object storage (immutable source artifacts)
   |---- Redis (queue/cache/rate coordination; non-authoritative)
   |---- Model/embedding/reranking providers (external processors)
   `---- Durable job publication
                  |
              Worker fleet
                  |---- parsers/sandboxed conversion boundary
                  |---- object storage / PostgreSQL / Redis
                  `---- external AI providers

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
| PostgreSQL | Tenants, memberships, sources, document versions, jobs, chunks, embeddings initially, evaluations, runs, audit references | Large source blobs, ephemeral locks as the only correctness mechanism |
| Object storage | Immutable uploaded/raw/derived artifacts with tenant-prefixed keys | Authorization decisions, mutable job state |
| Redis | Broker/queue coordination, cache, distributed rate/budget primitives | System of record |
| Provider adapters | Typed embedding/generation/reranking/tool interfaces, timeout/error normalization | Business policy |
| Retrieval subsystem | Candidate generation, filters, fusion, reranking, evidence/context assembly | Authorization bypass, free-form provider output |
| Evaluation subsystem | Versioned datasets/runs/metrics/comparisons | Production decisions without reviewed thresholds |
| Observability | Structured events, traces, metrics, cost/latency attribution | Raw sensitive document/prompt logging by default |

Logical code boundaries inside API/worker are `domain`, `application`, `infrastructure`, `retrieval`, `ai`, `api`, and worker entrypoints. Imports point inward: domain has no framework/provider dependencies; application depends on ports; infrastructure implements ports; routes and job consumers adapt external input.

## Current implemented baseline after Phase 2

The repository currently implements the control-plane foundation plus the storage and ingestion metadata slice: `apps/web`, `apps/api`, `apps/worker`, `packages/config`, and `packages/shared-types`. The API owns identity resolution, workspace use cases, RBAC policy, SQLAlchemy persistence, Alembic migrations, audit events, source/document/upload contracts, signed local upload handling, and OpenAPI export. The web app owns local sign-in UX, server-side BFF calls, workspace/member/source/document screens, direct-upload orchestration, Tailwind CSS styling, and security headers. The worker owns deterministic ingestion-job claiming, lease/version checks, object integrity verification, and metadata-only publication.

The implemented persistent tables are `users`, `workspaces`, `memberships`, `audit_events`, `idempotency_records`, `sources`, `upload_intents`, `documents`, `document_versions`, `ingestion_jobs`, and `job_events`. Local development uses a filesystem-backed object-store adapter with tenant-prefixed keys and HMAC-signed upload URLs; production object storage remains behind the same adapter boundary.

Phase 2 intentionally publishes document metadata only. Parsing, malware scanning, chunking, embeddings, retrieval, generation, evaluations, Redis-backed coordination, and external object-storage credentials remain deferred to later phases.

## Canonical data model

All tenant-owned tables include `workspace_id`, even when derivable, to make filtering, constraints, partitioning, auditing, and row-level defense possible. IDs are opaque UUIDs. Timestamps are UTC. Mutable records use optimistic versioning where concurrent edits matter.

- `users`: identity-provider subject and profile metadata.
- `workspaces`: tenant lifecycle and policy configuration.
- `memberships`: `(workspace_id, user_id)`, role, status; unique membership.
- `sources`: logical origin and source type; no secret values in ordinary columns.
- `documents`: stable logical document within a source/workspace.
- `document_versions`: immutable content version, object key, digest, media type, size, ingest status, parser provenance, active/publication state.
- `ingestion_jobs`: durable state machine, attempt count, idempotency key, lease/heartbeat, error class, progress, requested configuration.
- `chunks`: immutable chunk identity tied to document version; ordinal/page/span, text or protected text reference, token count, metadata, content hash, chunker version.
- `embedding_sets`: model/provider/dimension/configuration and lifecycle for migrations.
- `chunk_embeddings`: `(chunk_id, embedding_set_id)`, vector, status; coexistence enables model migration.
- `search_queries`: optional redacted/debuggable query execution metadata with retention controls.
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
3. In Phase 2, finalization creates the document, immutable document version, ingestion job, job event, audit event, and idempotency record in one PostgreSQL transaction.
4. The worker claims jobs with `FOR UPDATE SKIP LOCKED`, a lease owner, heartbeat timestamp, attempt counters, expected version, and bounded retry states.
5. Phase 2 worker execution verifies stored object size/digest and atomically publishes the document version as metadata-only. Later phases expand the state machine with malware/type policy, parsing, normalization, chunking, and embedding stages.
6. Cancellation is cooperative. Dead-letter state preserves diagnosable error metadata and a safe replay path.

### Search

1. API derives workspace/user authorization context; it never accepts workspace authority from the request alone.
2. Validate query, filters, limits, rate/cost budget, and visibility policy.
3. Generate lexical and semantic candidates over `READY` versions with identical tenant/ACL filters.
4. Fuse ranked lists (initially RRF), optionally rerank, and return typed evidence plus stage diagnostics when authorized.
5. Cache only with workspace, authorization fingerprint, index/version/config, and normalized-query keys; default to no cross-user cache until proven safe.

### Grounded answer

Search produces immutable evidence. Context construction deduplicates, applies per-source/total token budgets, orders to mitigate lost-in-the-middle, and labels untrusted excerpts. The generation adapter receives explicit instructions and typed evidence IDs. Post-processing parses a schema, checks cited IDs and quoted spans against supplied evidence, applies policy/output validation, and returns either a grounded answer with validation status or a safe degraded response—never invented citations.

### Bounded research

A LangGraph workflow is used only after deterministic RAG is measured. Run state and checkpoints are durable. Each tool has a schema, allowlist, authorization scope, timeout, cost, and output sanitizer. The loop has maximum steps/tokens/cost/wall time, explicit terminal states, and approval nodes for sensitive actions. Atlas begins with one orchestrated agent/workflow; multi-agent patterns remain a design exercise unless benchmarks justify them.

## API boundaries

Version public contracts under `/v1`. JSON uses stable error envelopes (`code`, `message`, `request_id`, safe `details`). Long work returns `202` plus a status resource. Pagination is cursor-based. Commands support an `Idempotency-Key` where replay is plausible.

Primary resource groups:

- `/v1/workspaces`, `/members`, `/roles` — tenancy and RBAC.
- `/v1/sources`, `/documents`, `/document-versions`, `/uploads` — source lifecycle.
- `/v1/ingestion-jobs/{id}` and cancellation/retry commands — asynchronous status.
- `/v1/search` — typed evidence and optional privileged debug stages.
- `/v1/answers` and `/answer-runs/{id}` — synchronous initially within strict timeout or asynchronous when needed.
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

OpenTelemetry provides vendor-neutral traces/metrics/log correlation; Langfuse captures redacted AI traces, evaluation metadata, prompt/model/config lineage, latency, tokens, and cost. Stable IDs connect HTTP requests, jobs, document versions, retrievals, answer runs, and research steps. Content capture is off by default and governed by tenant policy and retention.

Dominant cost drivers are model tokens, embeddings/re-embeddings, reranking, parser compute, vector/search storage, object storage/egress, database I/O, and trace retention. Quality changes require latency/cost/quality evaluation, not intuition alone.

## Evolution rule

PostgreSQL/pgvector, Redis, S3-compatible storage, and provider adapters are starting decisions, not permanent dogma. Architecture changes require evidence, an ADR entry, migration/rollback design, evaluation comparison, and an explanation the owner can defend. See `docs/decisions.md`, `docs/threat-model.md`, and `docs/roadmap.md`.
