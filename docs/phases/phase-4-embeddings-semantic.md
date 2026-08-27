# Phase 4 — Embeddings, pgvector, and semantic retrieval

## Scope

Add a provider-neutral embedding pipeline, batching/rate control, immutable embedding sets, pgvector storage/indexing, tenant-filtered semantic search, embedding backfill/migration, and a measurable brute-force/index baseline. Expose evidence, not answers.

## Engineering concepts

Embedding spaces, dimensions, normalization, cosine/dot/L2 distance, exact versus approximate nearest neighbors, HNSW/IVF concepts, recall-latency-memory tradeoffs, batching, rate limits, vector migrations, semantic-search failure modes, metadata filtering.

## Architecture changes and modules

Add embedding provider port/adapter with deterministic local fake as the default test/demo implementation, batch planner, rate/concurrency controller, embedding ingestion stage, embedding-set registry, semantic repository/retriever, index-management and backfill jobs. Search remains in the API query plane; heavy embedding work stays in workers.

## Data model changes

Add `embedding_sets` (provider/model/version/dimension/normalization/config/status) and `chunk_embeddings` keyed by chunk and set, with vector and completion status. Document publication requires the configured active set to be complete; old sets coexist during migration. Add vector index only after baseline/query plan inspection; dimension changes require new storage/index strategy, never in-place reinterpretation.

Phase 4 implementation note: the required zero-cost path stores deterministic normalized vectors in PostgreSQL JSONB and uses exact cosine ranking after tenant/status filtering. pgvector remains the first ANN/index candidate, but enabling it requires an explicit local image/extension migration plus recall/latency/query-plan evidence.

## APIs

`POST /v1/search/semantic` or unified `/v1/search` mode with query, typed metadata filters, `top_k`, and bounded authorized debug flag. Admin APIs/commands create backfill and inspect embedding-set coverage, not raw unrestricted vectors. Response `Evidence` includes chunk/version IDs, source span, snippet, distance/normalized score, embedding-set ID, and trace ID.

## Important interfaces

`EmbeddingProvider.embed(EmbeddingRequest[]) -> EmbeddingBatch`; `EmbeddingSetRegistry`; `EmbeddingBatchPlanner`; `SemanticRetriever.search(QuerySpec) -> Candidate[]`; `VectorIndexManager`; `BackfillCoordinator`. Provider errors normalize transient/permanent/resource-exhausted and preserve per-item outcomes where supported.

## Security requirements

Tenant/published/visibility filters execute inside the vector query, not after top-k; query length/metadata schemas and `k` are bounded; provider data-retention policy documented for any external provider; secrets isolated; sensitive text minimized; embedding inversion/linkability treated as risk; debug/raw vector endpoints privileged; per-tenant embedding/query budgets and redacted telemetry. Paid embedding APIs and large local model downloads are not required for the product gate.

## Failure scenarios

Partial provider batch; throttling/timeouts; wrong dimension/model response; duplicate retry; model removed or silently aliased; set migration interrupted; index build locks/space exhaustion; filter-selectivity collapses recall; DB query timeout; zero/invalid vectors. Never mix vectors from different spaces.

## Testing strategy

Adapter contract tests with deterministic fake; batching/idempotency/partial-failure tests; vector dimension/normalization tests; tenant/filter leakage tests; exact cosine implementation oracle; small labeled recall@k baseline; EXPLAIN/query-plan and latency checks at scenario sizes; dual-set migration/rollback test. Live provider checks are optional smoke tests only after explicit approval.

## Acceptance criteria

Published chunks have complete versioned embeddings; semantic results are authorized typed evidence; exact and ANN behavior can be compared; an interrupted embedding migration is resumable and reversible; baseline recall/latency/cost is recorded from the zero-cost deterministic path.

## Engineering review focus and implementation drills

Build intuition for similarity and indexes. Useful implementation drills: cosine similarity from scratch; batch planner under token/item limits; provider adapter error normalization; tenant-safe vector SQL; broken model-migration diagnosis; compute Recall@K on a labeled set.

## System-design review focus

Explain model/dimension choice, vector storage estimates, exact versus ANN, index parameter evidence, filter effects, re-embedding migration, provider failure halfway, database load, and when pgvector stops fitting.

## Explicit deferrals

No lexical/hybrid/reranking/generation. Exact production model, paid provider adoption, HNSW/IVF choice/parameters, compression, dedicated vector DB, and OpenSearch await corpus/load evidence and explicit opt-in for any billable execution. Do not tune against anecdotes.
