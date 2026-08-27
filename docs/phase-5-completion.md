# Phase 5 completion summary

## Scope completed

Phase 5 adds tenant-safe lexical and hybrid evidence retrieval on top of the existing ingestion, chunking, embedding, and semantic retrieval foundation.

Implemented:

- PostgreSQL full-text lexical retrieval over authorized ready chunks.
- GIN expression index for the English lexical baseline.
- Unified workspace-scoped search endpoint with `semantic`, `lexical`, and `hybrid` modes.
- Deterministic Reciprocal Rank Fusion over semantic and lexical ranked lists.
- Candidate deduplication by chunk plus document-version identity.
- Evidence responses with retrieval stage, branch ranks, branch scores, RRF score, trace ID, retrieval config version, and redacted debug metadata.
- Web search UI mode selector for Hybrid, Lexical, and Semantic retrieval.
- Deterministic Recall@K/MRR comparison utility for small labeled retrieval checks.
- OpenAPI and generated TypeScript contract updates.

## Architecture and security notes

- PostgreSQL remains the only authoritative retrieval store for the zero-cost path.
- Semantic and lexical branches apply the same workspace, active-document, ready-active-version, and allowlisted filter predicates before ranking.
- User queries are not persisted by default.
- Debug output is bounded to operational metadata: mode, retrieval config version, branch counts/status, rank/score provenance, and provider/config identifiers.
- No hosted search, cloud service, paid model API, or large local model download is required.

## Validation evidence

Commands completed successfully:

```bash
pnpm --filter @atlas/api db:migrate
pnpm --filter @atlas/api test
pnpm --filter @atlas/api openapi
pnpm --filter @atlas/shared-types generate
pnpm run lint
pnpm run typecheck
pnpm run test
pnpm run build
```

Observed results:

- API tests: `30 passed`.
- Worker tests: `4 passed`.
- Web tests: `1 passed`.
- Repository lint/typecheck/build: all packages successful.
- Phase 5 migration applied: `0004_phase4 -> 0005_phase5`.

## Failure and security scenarios validated

- Cross-tenant search requests return non-disclosing `404`.
- Empty and over-limit queries fail safely with validation errors.
- Special-character lexical queries are handled safely through parameterized PostgreSQL full-text search.
- Hybrid retrieval returns deterministic fused evidence with explicit branch counts/ranks.
- Backfill remains idempotent after Phase 5 changes.

## Zero-cost demonstration path

The Phase 5 demo uses:

- local PostgreSQL,
- local filesystem object storage,
- deterministic development auth,
- deterministic text/Markdown parser and chunker,
- deterministic local embeddings,
- PostgreSQL full-text search,
- RRF fusion,
- local API, worker, and web services.

No paid SaaS, hosted search, cloud resource, domain, hosted model API, or mandatory large local model is used.

## Deferred work

- Reranking, context construction, answer generation, and citation validation remain deferred to Phase 6.
- Evaluation datasets and retrieval quality gates remain deferred to Phase 7.
- Weighted/learned fusion, query rewriting, synonyms, multilingual analyzers, OpenSearch, pgvector ANN indexing, and caching optimizations require evidence from later evaluation or scale phases.
