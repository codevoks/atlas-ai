# Atlas AI

Atlas AI is a local-first enterprise knowledge and retrieval platform for teams that need trustworthy answers from their own documents. It combines workspace tenancy, document ingestion, hybrid search, grounded answers with verified citations, evaluation tooling, bounded research workflows, security guardrails, and operational visibility in one production-style monorepo.

The default development path is intentionally zero-cost: it runs locally with Docker, PostgreSQL, deterministic development auth, filesystem-backed object storage, deterministic local AI providers, and no paid cloud or model API calls.

## What problem does it solve?

Enterprise knowledge systems often fail because users cannot tell where an answer came from, administrators cannot audit access and risk, and engineering teams cannot evaluate retrieval quality before shipping changes. Atlas AI addresses those problems by making evidence, tenancy, provenance, safety controls, and evaluation data first-class parts of the product.

## Core capabilities

- Workspace-based tenancy with roles, membership management, and audit events.
- Direct text/Markdown document upload with signed local upload URLs, digest checks, durable ingestion jobs, parsing, normalization, chunking, and deterministic embeddings.
- Tenant-safe semantic, lexical, and hybrid evidence search backed by PostgreSQL.
- Grounded question answering that cites only retrieved workspace evidence and validates citations after generation.
- Versioned evaluation datasets and deterministic offline regression runs for retrieval, answer quality, and citation integrity.
- Bounded research workflows with budgets, checkpoints, tool provenance, approval gates, and cited report synthesis.
- Security guardrails for unsafe inputs, prompt-injection-like content, secret-like data, egress policy, quota enforcement, and admin-visible security events.
- Operations posture views with local telemetry, route metrics, dependency status, SLO summaries, capacity/cost posture, runbook links, CI/container artifacts, and plan-only infrastructure documentation.

## Technology overview

- Monorepo: pnpm workspaces and Turborepo.
- Web: Next.js App Router with Tailwind CSS.
- API: FastAPI with generated OpenAPI contracts.
- Worker: Python worker for durable ingestion and asynchronous processing.
- Database: PostgreSQL as the transactional source of truth.
- Object storage: local filesystem adapter for development, with production-grade adapter boundaries for S3-compatible storage.
- Retrieval and AI: deterministic local embedding, retrieval, reranking, generation, evaluation, and research adapters for reproducible zero-cost tests and demos.
- Infrastructure artifacts: Dockerfiles, Docker Compose for local PostgreSQL, GitHub Actions CI, and plan-only Terraform/AWS baseline with billable provisioning disabled by default.

## Prerequisites

- Node.js 22 or newer.
- pnpm 10.x.
- Python 3.12 or newer.
- Docker Desktop or a compatible Docker runtime.

## Local setup

Install JavaScript and Python dependencies:

```bash
pnpm install
python -m venv .venv
.venv/bin/pip install -e "apps/api[dev]" -e "apps/worker"
```

Create local environment configuration:

```bash
cp .env.example .env
```

For local development, replace the placeholder secrets in `.env` with any long random local-only values. These values are never suitable for production.

Start PostgreSQL and apply migrations:

```bash
docker compose up -d postgres
pnpm db:migrate
```

Generate API contracts:

```bash
pnpm --filter @atlas/api openapi
pnpm contracts
```

Start the services in separate terminals:

```bash
pnpm --filter @atlas/api dev
pnpm --filter @atlas/worker dev
pnpm --filter @atlas/web dev
```

Open the web app at [http://localhost:3000](http://localhost:3000).

## Local product walkthrough

1. Sign in with the deterministic local development flow.
2. Create or open a workspace.
3. Create a source for manual uploads.
4. Upload a UTF-8 `.txt`, `.md`, or `.markdown` document.
5. Let the worker ingest, parse, chunk, and embed the document.
6. Search workspace evidence with semantic, lexical, or hybrid retrieval.
7. Ask a grounded question and inspect the verified citations.
8. Review evaluation, research, security, and operations panels when available for your workspace role.

The local demo path uses deterministic providers and does not require hosted AI APIs, managed search, paid observability, cloud storage, a domain, or any billable cloud resource.

## Validation

Run the main repository checks:

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm ops:validate
```

The CI workflow runs local PostgreSQL, migrations, contract generation, artifact validation, linting, type checking, tests, and build checks without provisioning paid infrastructure.

## Configuration notes

- Development auth is allowed only for local development. Production settings reject development auth and require real OIDC/JWKS configuration.
- Optional cloud, managed observability, hosted search, external research tools, and model-provider integrations are adapter-compatible extension points, but they are disabled by default and require explicit operator configuration.
- Logs and telemetry are designed to avoid raw content capture by default.
- Never commit `.env`, private documents, secrets, raw sensitive provider payloads, or production traces.

## Documentation

Primary engineering references:

- `docs/architecture.md` — system architecture and component responsibilities.
- `docs/data-model.md` — persistent entities and invariants.
- `docs/threat-model.md` — security objectives, trust boundaries, risks, and controls.
- `docs/failure-model.md` — failure modes, retry ownership, and recovery behavior.
- `docs/capacity-model.md` — capacity assumptions and scaling boundaries.
- `docs/decisions.md` — architecture decision ledger and evidence gates.
- `docs/system-design-visuals.md` — current architecture, trust-boundary, data-flow, and reliability diagrams.
- `docs/operations-hardening.md` — observability, CI/container, runbook, and no-apply infrastructure guidance.

Historical engineering records are preserved under `docs/internal/`.
