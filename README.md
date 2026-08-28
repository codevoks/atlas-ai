# Atlas AI

Atlas AI is a production-grade enterprise knowledge and RAG SaaS built through explicit engineering phases. The repository currently contains the Phase 10 foundation: monorepo tooling, web/API/worker service boundaries, authentication seams, workspace tenancy, RBAC, idempotent workspace creation, audit events, source/document metadata, signed local upload intents, durable ingestion jobs, deterministic parsing and chunking for supported text formats, deterministic local embeddings, PostgreSQL lexical retrieval, tenant-safe semantic and hybrid evidence retrieval, deterministic grounded answers with verified citations, versioned evaluation datasets, deterministic offline RAG evaluation runs, evidence-gated query expansion, bounded multi-query retrieval planning, bounded research runs with checkpoints, tool provenance, budget enforcement, human approval, cited reports, centralized security guardrails, security-event visibility, quota counters, content-trust/retention data-model foundations, normalized derived artifacts, parser/chunker/embedding/retrieval/generation/evaluation/research/security provenance, and generated OpenAPI-to-TypeScript contracts.

## Current phase

Phase 10 — AI security, guardrails, and adversarial assurance.

Implemented:

- pnpm + Turborepo monorepo
- Next.js web/BFF in `apps/web`
- Tailwind CSS styling pipeline for the web app
- FastAPI control plane in `apps/api`
- durable ingestion worker surface in `apps/worker`
- PostgreSQL schema migrations for users, workspaces, memberships, audit events, idempotency records, sources, upload intents, documents, document versions, ingestion jobs, job events, chunks, embedding sets, and chunk embeddings
- development auth for deterministic local testing
- production OIDC/JWKS verifier boundary
- workspace/member APIs and typed web screens
- source, upload-intent, document, version, and ingestion-job APIs
- HMAC-signed local upload URL flow with digest and size verification
- lease/version-checked worker publication and upload-intent reconciliation endpoint
- deterministic text/Markdown parsing with binary and unsupported-format rejection
- canonical text normalization, derived normalized artifacts, and deterministic structure-aware chunks
- deterministic local hash embeddings with provider/model/version/dimension provenance
- tenant-safe semantic, lexical, and hybrid evidence search over ready active document versions
- PostgreSQL full-text lexical index and deterministic RRF fusion with branch rank diagnostics
- deterministic local grounded answer generation with verified source-span citations
- persisted answer runs, answer evidence, citations, prompt/model/config provenance, token/latency/cost metadata, and no hosted provider calls
- versioned evaluation datasets and immutable dataset versions with labeled cases
- deterministic offline retrieval/answer evaluation runs using production retrieval and answer services
- Recall@K, Precision@K, MRR, NDCG, answer coverage, citation coverage, and citation verification metrics with metric-version provenance
- evaluation run persistence, aggregate metrics, slice metrics, failure summaries, run listing UI, and auditable baseline approval
- allowlisted retrieval configurations, including the baseline RRF config and `phase8-multi-query-expansion-v1`
- deterministic query expansion with strict query-variant and branch fan-out budgets
- candidate aggregation with deduplication, optional diversity ordering, and transformed-query provenance
- search/answer/evaluation APIs that can run baseline-versus-candidate ablations without paid providers
- workspace UI controls for baseline versus Phase 8 retrieval configuration and visible retrieval-plan provenance
- workspace-scoped bounded research runs with persisted steps, tool invocations, checkpoints, approvals, budgets, usage, evidence, terminal reasons, and cited final reports
- deterministic local research graph with planner, Atlas retrieval tool, local policy-catalog tool, approval gate, and synthesis node
- research APIs for idempotent create, list, get, resume, cancel, and approval decisions
- workspace UI for starting research, inspecting run progress/tool provenance/checkpoints, approving synthesis, denying runs, and reading final reports
- deterministic input/output guardrails for indirect prompt injection, secret-like content, SSRF-like content, and unsafe generated output
- security-event persistence and admin-only security posture/event APIs
- fixed-window quota counters for abuse and denial-of-wallet protection on search, answer, and research operations
- egress policy, redactor, deterministic adversarial guardrail primitives, and security posture UI
- PostgreSQL foundations for versioned security policy configs, content trust records, quota counters, security events, and retention tombstones
- version, chunk, and evidence API responses with safe parser/chunker/embedding provenance and counts
- OpenAPI contract export and generated TypeScript types

Deferred:

- optional production S3-compatible storage, malware scanning, broad office/PDF/OCR parsing, pgvector ANN indexing, learned fusion, hosted reranking/generation, advanced citation analysis, hosted/LLM-judge evaluation, contextual chunk projections, external research tools, multi-agent runtime, enterprise DLP/KMS/HSM, external penetration testing, compliance certification, production cloud, billing, SAML/SCIM, and fine-grained document ACLs

## Zero-cost local path

Atlas must remain buildable, testable, and demonstrable without paid SaaS, cloud resources, domains, or paid model APIs. The current Phase 10 path uses local Docker/PostgreSQL, deterministic development auth, a filesystem-backed object-store adapter, local API/web/worker services, deterministic parser/chunker/embedding behavior, PostgreSQL full-text search, exact semantic search over stored normalized vectors, RRF hybrid fusion, deterministic query expansion, bounded multi-query planning, deterministic local generation, verified citation validation, deterministic local evaluation metrics, deterministic local research tools, approval-gated report synthesis, deterministic security guardrails, local quota counters, redacted security events, and no hosted model-provider calls.

Future cloud, managed observability, hosted search, and model-provider integrations are optional production adapters. They must be explicitly enabled and must not run or provision billable resources as part of the default setup, tests, or demo.

## Local setup

Install dependencies:

```bash
pnpm install
python -m venv .venv
.venv/bin/pip install -e "apps/api[dev]" -e "apps/worker"
```

Start PostgreSQL:

```bash
docker compose up -d postgres
pnpm db:migrate
```

Generate API contracts:

```bash
pnpm --filter @atlas/api openapi
pnpm contracts
```

Run validation:

```bash
pnpm lint
pnpm typecheck
pnpm build
pnpm test
```

Run services:

```bash
pnpm --filter @atlas/api dev
pnpm --filter @atlas/worker dev
pnpm --filter @atlas/web dev
```

The web app uses deterministic development sign-in locally. Production must use real OIDC/JWKS configuration; development auth is rejected in production settings.

## Engineering documentation

- `docs/architecture.md` — system architecture and component responsibilities
- `docs/system-design-visuals.md` — architecture and state-machine diagrams
- `docs/decisions.md` — cross-phase architecture decisions and evidence gates
- `docs/threat-model.md` — security objectives, trust boundaries, and phase reviews
- `docs/development-workflow.md` — phase workflow, validation, and repository hygiene
- `docs/project-status.md` — concise phase progress tracker
- `docs/phase-3-completion.md` — Phase 3 implementation and validation summary
- `docs/phase-4-completion.md` — Phase 4 implementation and validation summary
- `docs/phase-5-completion.md` — Phase 5 implementation and validation summary
- `docs/phase-6-completion.md` — Phase 6 implementation and validation summary
- `docs/phase-7-completion.md` — Phase 7 implementation and validation summary
- `docs/phase-8-completion.md` — Phase 8 implementation and validation summary
- `docs/phases/` — implementation contracts for each phase
