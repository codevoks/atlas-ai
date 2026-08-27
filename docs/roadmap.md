# Project blueprint and phase contract

## Delivery sequence

| Phase | Outcome | Primary evidence |
|---|---|---|
| 0 | Requirements, architecture, threat model, scale/failure reasoning, implementation plan | Architecture/design review |
| 1 | Monorepo, web/API seam, identity, workspaces, RBAC | Cross-tenant integration tests and live foundation demo |
| 2 | Source/object lifecycle and durable asynchronous ingestion | Duplicate/crash/retry state-machine tests |
| 3 | Safe parsing, normalization, chunking, metadata | Golden parser/chunker fixtures and resource-limit tests |
| 4 | Embedding lifecycle, pgvector, semantic retrieval | Recall/latency baseline and migration-safe provenance |
| 5 | Lexical + hybrid retrieval, RRF, filters, debug view | Retrieval ablations and tenant-filter parity tests |
| 6 | Reranking, context construction, grounded generation, citations | Citation-integrity and degraded-provider tests |
| 7 | Versioned evaluation platform and regression gates | Reproducible golden-set reports |
| 8 | Evidence-gated advanced RAG techniques | Ablation decision record with cost/latency/quality |
| 9 | Bounded LangGraph research workflow | Termination, checkpoint, budget, and tool-policy tests |
| 10 | Consolidated AI/security guardrails and adversarial assurance | Threat coverage and red-team regression suite |
| 11 | Scale-engine comparison, observability, AWS/Terraform, CI/CD, load/recovery hardening | Production readiness and benchmark report |

Each phase specification contains the mandatory scope, engineering concepts, architecture/data/API/interface changes, security requirements, failure scenarios, testing strategy, acceptance criteria, system-design expectations, and explicit deferrals. The `docs/phases/` files are implementation contracts; changes require an entry in `docs/decisions.md`.

## Phase gate protocol

Product gate evidence must include targeted tests, relevant integration/security/failure tests, lint, typecheck, build, migration forward/backward safety where relevant, dependency/resource impact, and exact results. Each phase must remain buildable, testable, and demonstrable at zero monetary cost. AI behavior tests must be deterministic by default; live-provider checks are opt-in smoke tests only and require explicit approval before any paid or hosted API is called.

Every implementation phase must end with a reproducible zero-cost demonstration before work stops for the next explicit authorization. Demonstrations should exercise the user/API/worker/security/failure behavior introduced by the phase and state honest limitations.

## Definition of implementation-grade

A phase is implementable without redesign when it identifies ownership, state transitions, persistent invariants, API/port shapes, error behavior, security boundaries, test evidence, migration/rollback needs, and deferrals. Exact library versions, model names, index parameters, chunk sizes, thresholds, and infrastructure sizes remain configuration or evidence-gated choices unless the phase explicitly fixes them.

## Evidence-gated evolution

The project intentionally starts with a small number of durable boundaries: web/BFF, API, worker, PostgreSQL, object storage, Redis, and provider adapters. More complex components require measured justification:

- Dedicated queue transport requires evidence that database-backed claiming is insufficient for throughput, isolation, delay/retry semantics, or operations.
- OpenSearch requires a documented scale or feature trigger plus shadow-read comparison against the PostgreSQL/pgvector baseline.
- Advanced RAG techniques require ablations showing quality benefit relative to cost, latency, and operational complexity.
- Runtime multi-agent designs require a named benchmark showing material benefit over a single bounded workflow.
- Deployment complexity should grow from measured availability, compliance, residency, and recovery requirements rather than defaulting to Kubernetes or multi-region architecture.

## Scenario-based capacity planning

Capacity estimates must declare their assumptions. A useful scenario defines active workspaces, documents per workspace, average bytes/document, chunks/document, query/answer QPS, daily uploads, model token sizes, and target SLOs. Storage, vector growth, index size, queue service rate, provider quota, and cost are derived from those variables. Production targets are accepted only after measurement and product requirements.
