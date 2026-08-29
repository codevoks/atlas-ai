# Phase 7 — Retrieval and RAG evaluation

## Scope

Create versioned golden datasets, offline evaluation runner, retrieval and answer metrics, Ragas adapters where useful, custom deterministic metrics, optional LLM-judge experiments with calibration, regression comparisons/gates, and a review workflow for human labels.

## Engineering concepts

Ground truth design, relevance grades, Recall/Precision@K, MRR, NDCG, answer correctness/faithfulness/groundedness/citation metrics, human evaluation, LLM-as-judge bias/variance, leakage, sampling, confidence/uncertainty, experiment lineage, latency/cost/quality Pareto analysis.

## Architecture changes and modules

Add dataset registry/import/export, evaluator ports, batch runner in worker, metric implementations, judge adapter with deterministic local fake by default, experiment comparison/report, and CI-sized deterministic regression subset. Evaluation calls production retrieval/answer interfaces with pinned configuration, not copied logic.

## Data model changes

Add `evaluation_datasets`, immutable dataset versions, `evaluation_cases` with query/relevance/expected claims/citations/slices, `evaluation_runs`, per-case `evaluation_results`, metric definitions/versions, configuration snapshots, reviewer labels, cost/latency, code/data revision. Sensitive corpora remain access-controlled and out of public fixtures.

## APIs

Admin/developer endpoints to create/version datasets, launch/cancel runs, inspect comparisons/slices/failures, and approve a baseline. Export must redact source content by policy. Production user APIs do not expose judge prompts or hidden expected answers.

## Important interfaces

`DatasetRepository`; `EvaluationRunner`; `RetrievalMetric`; `AnswerMetric`; `JudgeProvider`; `HumanReviewQueue`; `ExperimentComparator`; `RegressionPolicy`. Metric results include applicability, value, evidence, uncertainty/error, and version.

## Security requirements

Dataset tenant/access isolation; prevent production query ingestion without consent; PII/content redaction; judge prompts treat candidate outputs as untrusted; no expected-answer leakage into system under test; budget/rate limits; blind/randomized review where appropriate; audit baseline changes; protect evaluation from prompt injection and metric gaming. Paid judge/model APIs are opt-in only and not part of the default product gate.

## Failure scenarios

Missing/ambiguous labels; dataset leakage/overfitting; flaky judge; judge provider outage; config drift; partial run retry duplicates cost; metric silently inapplicable; corpus changed under dataset; aggregate hides bad tenant/slice; CI cost explosion. Results must distinguish system failure, metric failure, and missing evidence.

## Testing strategy

Hand-computed metric oracles; dataset schema/lineage tests; deterministic fake runner; resume/idempotency; judge repeatability/calibration against human labels using local fixtures; leakage checks; slice/aggregation tests; pinned small regression in CI; larger offline run at phase gate; compare retrieval separately from generation. Any live judge run requires explicit approval and is not required for completion.

## Acceptance criteria

Runs are reproducible from dataset/config/code/model lineage; custom metrics match oracles; retrieval and generation failures are separable; judge limitations are quantified; baseline regressions have explicit reviewed thresholds; reports include quality, latency, cost, slices, and qualitative failures.

## Engineering review focus and implementation drills

Useful implementation drills: Recall@K/MRR/NDCG from scratch; versioned dataset validator; resumable evaluation runner; diagnose leakage; calibrate an LLM judge; create and defend a regression policy.

## System-design review focus

Explain golden-set construction, metric selection, graded relevance, sampling bias, leakage, judge tradeoffs, statistical caution, offline-to-online mismatch, evaluation storage/scale, and how evidence gates architecture changes.

## Explicit deferrals

No automatic online experimentation, opaque “one score,” or production self-tuning. Advanced RAG/agent/OpenSearch decisions consume this platform later. Thresholds require baseline distributions and business risk, not arbitrary values.
