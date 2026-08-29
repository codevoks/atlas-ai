# Phase 5 — Lexical retrieval, hybrid search, RRF, filters, and debugging

## Scope

Implement PostgreSQL lexical search, a shared typed filter policy, parallel semantic/lexical candidates, RRF baseline fusion, deduplication, retrieval diagnostics, and offline retrieval comparisons. Keep the response as ranked evidence.

## Engineering concepts

Inverted indexes, tokenization/stemming, BM25 versus PostgreSQL ranking, exact-term/entity retrieval, hybrid complementarity, score calibration, RRF, metadata pre/post filtering, rank metrics, recall debugging, query analysis and cache safety.

## Architecture changes and modules

Add lexical index/projection fields and retriever, shared `QuerySpec`/filter compiler, concurrent candidate orchestration, fusion strategy, evidence formatter, privileged debug trace, and configuration registry. Both branches independently enforce the same authoritative policy predicates.

## Data model changes

Add language/configured text-search vector/index or derived lexical projection, retrieval configuration/version, and optional redacted query-run diagnostics with retention. Do not persist full user queries by default. No new authoritative document state.

## APIs

Unified `POST /v1/search` accepts query, mode (`semantic|lexical|hybrid`), safe metadata filters, bounded candidate/return counts, and optional privileged debug. Response contains final evidence and config/version; debug includes per-stage ranks/scores/timings/reasons without leaking hidden content or other tenants.

## Important interfaces

`LexicalRetriever`; `SemanticRetriever`; `FilterCompiler`; `HybridSearch.execute`; `FusionStrategy`; `RRF(k).fuse`; `CandidateDeduplicator`; `SearchDiagnosticsSink`. Candidate identity is chunk+document-version; raw branch scores remain branch-specific.

## Security requirements

Allowlisted typed filters; parameterized queries; tenant/visibility/published predicates inside each branch; maximum query/candidate complexity; privileged/redacted debug data; workspace+authorization+config-aware cache keys; rate limits; no result-count side channel across tenants.

## Failure scenarios

One branch timeout; lexical tokenizer/language mismatch; vector index unavailable; duplicate candidates; stale lexical projection; filter applied only after top-k; empty/stopword query; adversarial wildcard/filter complexity; branch latency imbalance. Partial results must be labeled and must never relax policy.

## Testing strategy

RRF from-scratch unit/property tests; fixed candidate fusion oracles; SQL/filter parity and cross-tenant tests; one-branch timeout/degradation tests; end-to-end exact term and paraphrase cases; Recall@K/MRR/NDCG comparisons across modes; query-plan/load checks; debug redaction snapshots.

## Acceptance criteria

Hybrid search measurably compares with each branch on a labeled set; exact and semantic cases are diagnosable; every branch has identical authorization constraints; fusion is deterministic; partial degradation is explicit; configuration/provenance makes results reproducible.

## Engineering review focus and implementation drills

Useful implementation drills: lexical query/index; RRF implementation; filter-compiler security tests; calculate MRR/NDCG; debug post-filter recall loss; compare fusion methods on fixed ranked lists.

## System-design review focus

Explain why hybrid works, when it does not, rank versus score fusion, RRF constant tradeoff, prefilter/index effects, parallel latency, cache authorization, OpenSearch feature triggers, and retrieval debugging order.

## Explicit deferrals

No reranking/context/generation. Weighted/learned fusion, synonyms, multilingual analyzers, query rewriting, OpenSearch, and caching optimizations need Phase 7/8 or Phase 11 evidence.
