# Atlas AI

Atlas AI is a production-grade enterprise knowledge and RAG SaaS built through explicit engineering phases. The repository currently contains the Phase 4 foundation: monorepo tooling, web/API/worker service boundaries, authentication seams, workspace tenancy, RBAC, idempotent workspace creation, audit events, source/document metadata, signed local upload intents, durable ingestion jobs, deterministic parsing and chunking for supported text formats, deterministic local embeddings, tenant-safe semantic evidence retrieval, normalized derived artifacts, parser/chunker/embedding provenance, and generated OpenAPI-to-TypeScript contracts.

## Current phase

Phase 4 — deterministic embeddings and semantic evidence retrieval.

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
- tenant-safe semantic evidence search over ready active document versions
- version, chunk, and evidence API responses with safe parser/chunker/embedding provenance and counts
- OpenAPI contract export and generated TypeScript types

Deferred:

- optional production S3-compatible storage, malware scanning, broad office/PDF/OCR parsing, lexical/hybrid retrieval, pgvector ANN indexing, reranking, RAG answer generation, evaluation, agents, production cloud, billing, SAML/SCIM, and fine-grained document ACLs

## Zero-cost local path

Atlas must remain buildable, testable, and demonstrable without paid SaaS, cloud resources, domains, or paid model APIs. The current Phase 4 path uses local Docker/PostgreSQL, deterministic development auth, a filesystem-backed object-store adapter, local API/web/worker services, deterministic parser/chunker/embedding behavior, exact semantic search over stored normalized vectors, and no hosted model-provider calls.

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
- `docs/phases/` — implementation contracts for each phase
