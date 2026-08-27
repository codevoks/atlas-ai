# Capacity, scaling, and cost model

Atlas capacity plans are scenario worksheets. Values are not product facts until observed or agreed.

## Variables

| Symbol | Meaning |
|---|---|
| `W`, `U` | active workspaces and users |
| `D`, `B` | retained documents and mean source bytes/document |
| `V` | mean retained versions/document |
| `C_d`, `T_c` | mean chunks/document-version and tokens/chunk |
| `d`, `p` | embedding dimensions and bytes/component |
| `Q_s`, `Q_a` | peak search and answer requests/second |
| `K_s`, `K_l`, `K_r` | semantic, lexical, and rerank candidate depths |
| `L_u`, `S_p` | peak ingestion arrivals/second and sustainable documents/worker-second |
| `R`, `N` | concurrent research runs and maximum steps/run |

## First-order estimates

- Source bytes: `D × V × B` before object versioning, replicas, derived artifacts, and lifecycle savings.
- Chunks: `C = D × V × C_d` before dedup/retention.
- Raw vector bytes per embedding set: `C × d × p`. Measure row/index/WAL/replica overhead separately; do not use raw bytes as provisioned storage.
- Phase 4 stores deterministic normalized vectors as PostgreSQL JSONB and ranks with exact cosine after tenant/status filtering. This is the zero-cost correctness baseline. It must be replaced or shadow-compared with pgvector ANN only after measured corpus size, query-plan, recall, latency, and storage evidence justify the migration.
- Embedding tokens for a full set: approximately `C × T_c`, plus any contextualization prefixes and retries.
- Search candidate flow: `Q_s × (K_s + K_l)` before fusion/dedup; reranker work is `Q_s × K_r` when enabled.
- Model tokens/day: sum actual instruction/query/context/output tokens for answers, reranking/rewriting/judging, evaluation, research steps, and retries. Attribute to successful outcome and tenant/config.
- Ingestion stability requires aggregate sustainable service rate greater than sustained arrival. Approximate required workers as `ceil(peak arrival / measured per-worker service rate)` with headroom; model each stage separately because parse and embedding bottlenecks differ.
- Research worst-case calls are bounded by `R × N`, further constrained by per-run/global tool, token, cost, wall-time, and concurrency budgets.

## SLO-linked workload scenarios

For each expected/peak/skew scenario record corpus/tenant distribution, query mix, filter selectivity, upload types/sizes, provider quotas, concurrency, target freshness and latency, availability window, retention, and RTO/RPO. Test with representative small safe fixtures scaled synthetically; quality tests need real labeled distributions, while load data must not contain private content.

## Measure and graph

- HTTP/search/answer p50/p95/p99 latency and error by stage/config.
- Queue arrival/completion, oldest age, attempts, stage duration, poison count, tenant fairness.
- Parser CPU/memory/temp bytes and failures by type.
- DB connections, CPU, IOPS, cache hit, locks, query plans, table/index/WAL growth.
- Vector exact/ANN recall versus latency/memory and filter selectivity.
- Provider latency/errors/throttles/tokens, batch utilization, cost.
- Research concurrency, steps, termination reasons, budget exhaustion.
- Object/backup/trace storage growth and restore/reindex duration.

## Likely bottlenecks and responses

Provider quotas/latency: batch, bound concurrency, backpressure, caching only when safe, degrade, negotiate quota/provider strategy. Parser CPU/memory: isolated pools by workload, limits, autoscale from queue age. Database: query/index tuning, pooling, batching, replicas for safe reads, partition/tenant placement. Vector retrieval: evaluate index/filter strategy, compression/dedicated projection. Context/model cost: better retrieval/context budgets, smaller justified model, caching with authorization/version keys. Noisy tenants: per-tenant queues/concurrency/rates/budgets and large-tenant placement.

## Evidence gates

OpenSearch needs representative PostgreSQL search failure or required features plus shadow quality/latency/cost/operational comparison. Microservices need independent scale/failure/ownership pressure. Multi-region needs explicit availability/residency/RTO/RPO. Advanced RAG and agents need quality improvement on named slices after added latency/cost/failure. Infrastructure size is selected from measured load, not repository documentation.
