# Phase 4 completion — embeddings and semantic retrieval

Phase 4 extends the ingestion pipeline from chunk publication to searchable semantic evidence. Published document versions now include deterministic embedding coverage for every chunk in the configured active embedding set.

## Product capabilities

- Provider-neutral embedding contracts with a deterministic local hash embedding provider for the default zero-cost path.
- Bounded embedding batch planning and dimension/normalization validation.
- Workspace-scoped immutable `embedding_sets` and `chunk_embeddings` persistence.
- Worker ingestion state `EMBEDDING` between chunking and publication.
- Atomic publication of chunks, embeddings, provenance, and ready document-version metadata.
- Workspace-scoped semantic evidence API at `POST /v1/workspaces/{workspace_id}/search/semantic`.
- Idempotent admin backfill API at `POST /v1/workspaces/{workspace_id}/embeddings/backfill` for missing active-set embeddings.
- Web workspace search panel that displays evidence snippets, scores, distances, trace IDs, and embedding provenance.

## Architecture notes

PostgreSQL remains the authoritative state boundary. Phase 4 stores deterministic normalized vectors as JSONB and ranks with exact cosine similarity after tenant/status filtering. This preserves the zero-cost local path on the existing plain PostgreSQL compose image.

pgvector remains the first indexed-vector candidate. Enabling HNSW/IVF requires an explicit image/extension migration plus recall, latency, query-plan, and storage evidence against this exact baseline.

## Validation summary

- API lint and formatting.
- API mypy typecheck.
- API tests including embedding provider contracts, tenant-safe semantic retrieval, invalid query bounds, and publication provenance.
- Worker lint, typecheck, and tests.
- Web lint, typecheck, and production build.
- Full monorepo lint, typecheck, test, and build gates.

## Deferred scope

- Lexical retrieval, hybrid fusion, RRF, and retrieval debugging.
- Reranking, answer generation, context construction, and citation validation.
- Hosted embedding providers, paid APIs, large local LLM downloads, and managed vector/search services.
- pgvector ANN index adoption until benchmark evidence justifies the migration.
- Long-running multi-set backfill orchestration and progress UI beyond the bounded idempotent repair command.
