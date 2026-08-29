# Phase 8 completion — Evidence-gated advanced RAG

## Summary

Phase 8 adds one advanced RAG technique behind an explicit retrieval configuration: deterministic bounded query expansion with multi-query retrieval planning. The feature is intentionally narrow, zero-cost, observable, and reversible. It was enabled because a reproducible Phase 7-style ablation showed a vocabulary-mismatch slice improving without paid providers, tenant-scope changes, or hidden model behavior.

## What changed

- Added `phase8-multi-query-expansion-v1` as an allowlisted retrieval configuration beside the Phase 5 baseline `phase5-postgres-fts-rrf-v1`.
- Added a deterministic query transformer with fixed expansion mappings, injection-like query suppression, maximum query-variant limits, and recorded fan-out budgets.
- Extended search, answer, and evaluation APIs to accept an authorized named retrieval configuration.
- Added multi-query retrieval planning across semantic/lexical/hybrid modes with bounded per-branch candidates, deduplication, RRF/best-score aggregation, and optional document-diversity ordering.
- Added transformed-query provenance to search evidence and persisted answer evidence.
- Extended evaluation cases/runs so the same dataset can compare baseline and candidate retrieval configurations.
- Added workspace UI selectors for baseline versus Phase 8 retrieval configuration and visible retrieval-plan provenance.

## Evidence and tradeoff

The targeted Phase 8 fixture covers a vocabulary mismatch:

- Query: `payment authorization`
- Relevant text: `Invoices require finance approval for SAML access before payment is released.`
- Baseline lexical retrieval with `phase5-postgres-fts-rrf-v1` returns no evidence because the query contains `authorization` while the corpus uses `approval/access`.
- Candidate retrieval with `phase8-multi-query-expansion-v1` generates bounded variants including `invoice approval finance access`, retrieves the relevant chunk, and preserves evidence provenance.

Observed ablation in automated tests:

- Baseline Recall@K: `0`
- Phase 8 Recall@K: `1`
- Phase 8 citation verified rate: `1`
- Phase 8 cost: `$0.00`

The enabled technique is accepted only for this narrow, deterministic vocabulary-mismatch improvement. It is not evidence for hosted rewriters, learned fusion, contextual embeddings, OpenSearch, personalization, or agents.

## Security and reliability notes

- API schemas and service validation reject unsupported retrieval configuration names.
- Query expansion does not change tenant, source, document, active-version, or membership predicates.
- Injection-like query text suppresses expansion and records a warning.
- Hidden evaluation labels are not passed to retrieval or generation.
- All default tests and demos use deterministic local execution only.

## Validation

The Phase 8 gate requires:

- Alembic migration upgrade to `0008_phase8`.
- OpenAPI export and TypeScript contract generation.
- API/web/shared lint and typecheck.
- API, worker, and web tests.
- Production build.
- Zero-cost live demo showing baseline failure, Phase 8 recovery, evaluation ablation, UI retrieval plan, invalid config rejection, and cross-tenant denial.

## Deferred work

- Contextual chunk enrichment/projections and contextual embeddings.
- Learned or weighted fusion.
- Hosted query rewriters, rerankers, judges, and LLM-based expansion.
- LlamaIndex integration.
- OpenSearch or ANN migration.
- Online experimentation, personalization, automatic promotion, and self-tuning.

