# Atlas AI product engineering charter

Atlas AI is a production-grade, multi-tenant enterprise knowledge, retrieval-augmented generation, and bounded-research SaaS. The repository should be understandable to engineers, reviewers, operators, and future implementation agents without relying on private context.

## Primary product objective

Build a defensible SaaS platform that can:

- securely ingest enterprise knowledge sources;
- preserve tenant isolation across every row, object, job, cache key, index, trace, and generated answer;
- process uploaded content through durable asynchronous ingestion;
- support lexical, semantic, and hybrid retrieval over authorized evidence;
- generate grounded answers with verifiable citations;
- run bounded research workflows with explicit budgets, checkpoints, approvals, and tool policies;
- expose observable quality, latency, cost, and security behavior; and
- evolve from a simple local baseline to production deployment only when measurements justify added complexity.

## Public repository standard

This public repository must read like a professional SaaS engineering project. Keep architectural depth, design rationale, test strategy, threat models, ADRs, phase contracts, operational constraints, and benchmark methodology in public docs. Do not place private/personal material or sensitive local paths in public artifacts.

All public material must be written in professional English.

## Engineering principles

- Correctness and tenant isolation are product requirements, not optional hardening.
- PostgreSQL is the initial transactional source of truth.
- Object storage owns immutable source blobs and derived artifacts.
- Redis is ephemeral coordination/cache only; it is never authoritative.
- pgvector starts as the semantic store; OpenSearch or another projection requires benchmark evidence.
- Every asynchronous effect is modeled with durable state, stable idempotency keys, leases, bounded retries, timeouts, and diagnosable failure states.
- External providers are wrapped behind narrow adapters with normalized errors and persisted provider/model/version provenance.
- Retrieval returns typed evidence with stable document/chunk/version identity.
- Generation may cite only evidence supplied by retrieval; citations are validated after generation.
- Uploaded files, retrieved content, web content, model output, and tool output are untrusted data.
- Agents and multi-agent workflows require bounded tools, budgets, termination criteria, observability, and benchmark evidence.

## Target stack

The planned baseline stack is:

- TypeScript
- React
- Next.js App Router
- Tailwind CSS
- Python
- FastAPI
- PostgreSQL
- pgvector
- Redis
- S3-compatible object storage
- OpenAI and/or equivalent model providers through adapters
- OpenTelemetry
- Langfuse
- Docker
- Terraform
- AWS-oriented production deployment
- GitHub Actions

Use the simplest implementation that preserves the required architectural boundaries. Add infrastructure or service decomposition only when a phase specification or measured evidence requires it.

## Repository architecture

Required monorepo structure:

```text
apps/
  web/       # Next.js browser-facing UI/BFF
  api/       # FastAPI control/query plane
  worker/    # Durable asynchronous processing
packages/
  config/        # shared TS/tooling config
  shared-types/  # generated API contracts
docs/
  phases/        # phase implementation specifications
```

Initial responsibilities:

- `apps/web`: browser UI, session UX, server-side BFF calls, safe rendering, Tailwind styling.
- `apps/api`: authentication context, authorization, domain use cases, transactions, REST contracts, retrieval/RAG orchestration.
- `apps/worker`: ingestion/reindex/research jobs, leases, retries, checkpoints, failure recovery.
- PostgreSQL: authoritative metadata, identities, workspaces, jobs, document versions, chunks, embeddings initially, answer/research/evaluation lineage, and audit events.
- Object storage: immutable source and derived artifacts.
- Redis: queue coordination, short-lived cache, rate/budget coordination where safe.

## Phase discipline

Implementation proceeds one phase at a time. Do not start the next phase until explicitly authorized.

Each phase must include:

- scope;
- engineering concepts;
- architecture changes;
- components/modules;
- data model changes;
- APIs;
- important interfaces;
- security requirements;
- failure scenarios;
- testing strategy;
- acceptance criteria;
- system-design decisions and tradeoffs;
- explicit deferrals; and
- a reproducible demonstration when implementation exists.

The current public phase contracts live under `docs/phases/`.

## Cross-phase architecture decisions

Resolved decisions live in `docs/decisions.md`. Future changes that affect stores, trust boundaries, job semantics, retrieval architecture, AI provider behavior, evaluation gates, deployment model, or tenant isolation must update the decision ledger and the relevant architecture/threat-model documents.

Important decisions already fixed:

- pnpm + Turborepo monorepo.
- Next.js web/BFF, FastAPI API, separate worker.
- PostgreSQL as source of truth, object storage for blobs, Redis non-authoritative.
- Tenant scope is explicit everywhere.
- Idempotent, at-least-once state machines for ingestion and research.
- Immutable document versions, chunks, embedding sets, answer evidence, and citation lineage.
- OpenAPI as the public API contract source for TypeScript generation.
- Deterministic RAG before agentic research.
- No runtime multi-agent architecture without benchmark evidence.

## System design visuals

Keep `docs/system-design-visuals.md` synchronized when boundaries, stores, trust zones, data flows, state machines, or scaling paths change. Prefer small Mermaid diagrams that clarify ownership and flow rather than decorative diagrams.

## Security model

Security requirements are cumulative across phases. At every phase:

- update assets and trust boundaries when the architecture changes;
- enforce server-side authorization at use-case and persistence boundaries;
- add cross-tenant and negative tests for new resource types;
- treat external content and model outputs as untrusted;
- redact secrets and sensitive content from logs/traces;
- document residual risks and operational controls; and
- keep production settings fail-closed.

The canonical threat model is `docs/threat-model.md`.

## Evaluation and benchmark policy

Retrieval, generation, reranking, chunking, provider selection, agent workflow complexity, OpenSearch adoption, and scaling changes must be driven by evidence. Benchmarks should record:

- dataset/corpus version;
- workload assumptions;
- retrieval/generation configuration;
- quality metrics;
- latency percentiles;
- cost;
- failure slices;
- operational complexity; and
- rollback plan.

Do not promote a more complex architecture only because it is fashionable.

## Phase completion requirements

Before marking an implementation phase complete:

- run the relevant migration and validation commands;
- run lint, typecheck, build, tests, and contract generation where applicable;
- demonstrate the user/API/worker/security/failure behavior introduced in the phase;
- update public architecture, decisions, threat model, visuals, and phase completion docs;
- verify local secrets, generated artifacts, dependency folders, private notes, and sensitive data are not tracked by Git; and
- record honest limitations and deferred scope.

Then stop and wait for explicit authorization for the next phase.
