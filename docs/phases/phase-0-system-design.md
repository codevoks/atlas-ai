# Phase 0 — System design, requirements, and threat model

## Scope and deliverables

Produce and review the complete pre-implementation design: `docs/architecture.md`, `docs/decisions.md`, `docs/threat-model.md`, `docs/roadmap.md`, all later phase contracts, and this repository guidance. No application scaffold, runtime dependency, database, infrastructure, or production code belongs in Phase 0.

Product assumptions to validate later: Atlas begins as a workspace-scoped SaaS; users upload supported documents; workspace members search and ask grounded questions; admins manage sources/members; ingestion and research are asynchronous where work exceeds request latency; initial visibility is workspace-wide with role-gated administration; a single region and one baseline model provider per capability are adequate before production requirements say otherwise.

Functional requirements:

- Authenticate users; create/select workspaces; manage membership and roles.
- Upload, version, list, inspect, delete, and reprocess sources/documents.
- Expose durable ingestion status, progress, error class, retry, and cancellation.
- Search authorized published content with semantic, lexical, hybrid, filters, and evidence metadata.
- Generate grounded answers from evidence with verifiable citations and safe degraded outcomes.
- Curate/version evaluation cases and compare retrieval/RAG configurations.
- Run bounded research workflows with approved tools, checkpoints, budgets, audit, and intervention.
- Provide administrative auditability, observability, usage/cost attribution, retention/deletion controls.

Non-functional requirements are the architecture invariants in `docs/architecture.md`: isolation, durability, idempotency, explicit consistency, safe failure, reproducibility, observability, maintainability, resource bounds, and evidence-based scalability. Numeric SLOs/RTO/RPO/data-residency promises require stakeholder input and measurement; Phase 0 defines how to derive them, not fictional values.

## Engineering concepts

Requirements decomposition; functional versus non-functional requirements; capacity variables; control/query plane versus worker; source-of-truth versus derived projection; sync/async decisions; consistency and availability; idempotency and effective-once effects; tenancy/trust boundaries; retrieval/RAG stages; failure domains; cost drivers; evolutionary architecture; ADRs; threat modeling; product gates.

## Architecture, components, and data model

Architecture and ownership are specified in `docs/architecture.md`; persistent entities and invariants are canonical there. Phase 0 adds no deployed component or schema. The design review must verify browser, web/BFF, API, worker, PostgreSQL/pgvector, object storage, Redis, providers, and later OpenSearch boundaries, including authoritative state, untrusted inputs, asynchronous transitions, and tenant enforcement points.

## APIs and important interfaces

Define resource boundaries and conceptual ports before framework code: identity/authorization, object store, unit of work, durable job repository, parser, chunker, embedding provider, semantic/lexical retriever, fusion, reranker, context builder, generator, citation validator, evaluation metric, research tool, and budget ledger. The required semantics are in `docs/decisions.md`; exact signatures and transport schemas are refined in their owning phase without weakening scope, provenance, timeout, cancellation, and error taxonomy.

## Security requirements

Complete asset/actor/boundary analysis; define server-derived tenant context; classify uploads, retrieval, model/tool output as untrusted; require least privilege, tenant-scoped storage and telemetry, provider secret/data handling, cost/abuse controls, safe logging, secure deletion, and phase-local negative tests. Residual risks and deferred controls must be explicit. See `docs/threat-model.md`.

## Failure scenarios

Reason through upload finalized but job publication interrupted; duplicate/stale worker; parser crash or malicious file; embedding batch partially failing or rate-limited; Redis loss; PostgreSQL failover; object missing/corrupt; one retrieval branch unavailable; model timeout; invalid/fabricated citations; membership revoked mid-request; cache/index staleness; tool prompt injection; budget race; observability exporter outage; region loss. For each identify detection, authoritative state, retryability, user-visible state, containment, recovery, and data-integrity invariant.

## Testing and review strategy

Phase 0 validation is documentary: link/invariant review, requirement-to-phase trace, data-flow/threat walkthrough, failure-table review, capacity worksheet, and API boundary review. Verify public development guidance is concise, later phases contain all mandated headings, local/private paths are ignored, and private/personal material is not tracked.

## Acceptance criteria

- Every required prompt topic maps to architecture or a phase contract; no implementation has begun.
- Major entities, read/write flows, sync/async boundaries, consistency classes, trust boundaries, cost/scaling variables, bottlenecks, failure recovery, and alternatives are defensible.
- Cross-phase invariants and evidence-gated choices are recorded; later phases cannot drift silently.
- Public documentation contains the full implementation blueprint without private/personal workflow material.
- Git ignore rules exclude local notes, dependencies, build artifacts, and secrets.

## Engineering review focus and implementation drills

The design review should derive architecture from requirements, estimate resources symbolically, defend stores/boundaries, and reason about failures rather than name technologies. Useful implementation drills include: implement a tiny idempotent job-transition function; calculate chunk/vector/token/queue load from a supplied scenario; model a tenant-aware authorization decision; classify retryable errors; write an RRF-free retrieval flow interface; and debug a dual-write failure narrative.

## System-design review focus

Explain why ingestion is asynchronous; why blobs are outside PostgreSQL; why pgvector first; lexical + semantic complementarity; when OpenSearch earns its cost; tenant enforcement layers; partial embedding recovery; strong versus eventual consistency; first 100× bottlenecks; a 10M-document redesign; derived-index rebuild; provider abstraction; citation integrity; agent versus workflow; multi-agent coordination cost.

## Explicit deferrals

All production implementation is deferred. Numeric SLOs, model/provider selection, chunk parameters, index tuning, queue transport, RLS adoption, OpenSearch, advanced RAG, agent topology, AWS sizing, and multi-region design require later phase requirements or benchmark evidence. Do not create scaffolding “to save time.”

## Gate

`PRODUCT GATE: PASS` only when all Phase 0 public artifacts and privacy checks are complete.
