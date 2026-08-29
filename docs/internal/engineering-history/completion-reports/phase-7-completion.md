# Phase 7 completion — Retrieval and RAG evaluation platform

## Summary

Phase 7 adds a zero-cost, deterministic offline evaluation platform for retrieval and grounded-answer behavior. It introduces versioned golden datasets, immutable labeled cases, evaluation runs over the production retrieval and answer services, deterministic metric computation, aggregate/slice/failure reporting, web visibility for latest runs, and append-only baseline approval.

## What changed

- Added workspace-scoped evaluation tables for datasets, immutable dataset versions, labeled cases, runs, per-case results, and baseline approvals.
- Added evaluation APIs to create/list datasets, create dataset versions, launch runs, inspect runs/results, and approve baselines.
- Added deterministic metrics for Recall@K, Precision@K, MRR, NDCG, answer fragment coverage, citation quote coverage, and citation verified rate.
- Added an evaluation runner that calls the existing production retrieval and answer services with pinned configuration instead of duplicating RAG logic.
- Added latest evaluation-run visibility to the workspace UI so regression results are visible beside search and grounded-answer workflows.
- Added tests covering metric oracles, dataset/run/baseline flow, tenant isolation, and invalid relevant-chunk labels.

## Architecture and security notes

- Evaluation labels are not passed to retrieval or generation; they are used only after the system-under-test produces outputs.
- Relevant chunk labels are accepted only when they point to ready active chunks in the same workspace.
- Evaluation records are workspace-scoped and protected by the existing membership/RBAC boundary.
- Baseline approval requires workspace-update permission and creates an append-only approval record.
- The default evaluation path uses deterministic local metrics only. Hosted judges, paid model APIs, cloud resources, and large local model downloads remain disabled.

## Validation

The Phase 7 gate requires:

- Alembic migration upgrade.
- OpenAPI export and generated TypeScript contract refresh.
- API lint, typecheck, and test suite.
- Web lint, typecheck, and production build.
- Root lint, typecheck, test, and build workflows.
- Zero-cost demo covering a normal evaluation run, invalid-label failure, cross-tenant denial, baseline approval, and UI run visibility.

## Deferred work

- Redacted import/export of evaluation corpora.
- Asynchronous/resumable large evaluation runs through the worker.
- Human-review queue, blind/randomized review, and reviewer-assignment workflows.
- Hosted LLM judges and calibration experiments.
- Hard regression thresholds and automatic promotion/rollback gates.
- Online experimentation and production self-tuning.

