# Development workflow

Atlas AI is implemented through explicit engineering phases. The phase specifications in `docs/phases/` are the implementation contracts; architecture changes require updates to the relevant design documents and the decision ledger.

## Phase discipline

- Work on one approved phase at a time.
- Do not begin the next phase until its scope is explicitly approved.
- Keep implementation, tests, security review, failure handling, documentation, and demonstration evidence aligned with the active phase specification.
- Record architecture changes in `docs/decisions.md`.
- Update `docs/architecture.md`, `docs/threat-model.md`, and `docs/system-design-visuals.md` when component boundaries, authoritative stores, trust boundaries, major data flows, state machines, or scaling decisions change.

## Validation expectations

Before a phase is considered complete, run the relevant subset of:

```bash
pnpm --filter @atlas/api openapi
pnpm contracts
pnpm lint
pnpm typecheck
pnpm build
pnpm test
```

Phases with database changes must also run the migration path against local PostgreSQL:

```bash
docker compose up -d postgres
pnpm db:migrate
```

Implementation evidence should include real command output and, where practical, an end-to-end local demonstration of the user/API/worker/security/failure behavior introduced by the phase.

## Security and repository hygiene

- Keep secrets, local environment files, private notes, generated object-store data, dependency folders, caches, and build outputs out of Git.
- Public documentation must remain professional engineering documentation.
- Do not commit private/personal material, raw sensitive documents, provider payloads containing customer data, production traces, or local automation instructions.
- Logs and telemetry must be redacted and tenant-safe.
- Treat uploads, retrieved content, web content, model output, and tool output as untrusted data.

## Architecture evolution

The baseline architecture intentionally starts with a small number of durable boundaries: Next.js web/BFF, FastAPI API, worker, PostgreSQL, object storage, Redis, and provider adapters. More complex infrastructure such as a dedicated queue transport, OpenSearch projection, advanced RAG techniques, runtime multi-agent patterns, or more complex deployment topologies requires documented evidence and a rollback plan.
