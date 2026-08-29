# Phase 8 — Evidence-gated advanced RAG

## Scope

Use Phase 7 to test query rewriting, multi-query retrieval, decomposition, contextual retrieval/chunk enrichment, diversity, and other selected techniques one at a time. Implement only techniques that improve named slices enough to justify latency, cost, complexity, and new failure modes; ship configuration/rollback and an ablation report. The default ablation path must use deterministic local execution and require no paid model APIs.

## Engineering concepts

Query intent/rewriting, expansion versus drift, multi-query recall/dedup, decomposition, hypothetical-document ideas and risks, contextual embeddings/retrieval, parent-child retrieval, diversity/MMR, adaptive routing, ablation and Pareto tradeoffs.

## Architecture changes and modules

Add a versioned query transformation pipeline, optional context-enrichment ingestion projection, retrieval-plan executor with strict fan-out budget, result provenance linking original and transformed queries, feature/config registry, and experiment switches. LlamaIndex may be used only for a component whose behavior remains understood, replaceable, observable, and benchmarked against the custom baseline.

## Data model changes

Add retrieval-plan/config versions, transformed-query provenance, optional contextualized chunk projection/version, experiment assignment, and comparison metadata. Never overwrite original chunks or embeddings; migration and rollback use new projections/embedding sets.

## APIs

Existing search/answer APIs accept an authorized named retrieval configuration, not arbitrary client prompt templates. Privileged debug shows original/transformed queries, branch/fan-out, dedup, timings, cost, and final evidence. Admin experiment APIs compare and promote/rollback configurations.

## Important interfaces

`QueryTransformer`; `RetrievalPlanner`; `SubqueryBudget`; `CandidateAggregator`; `DiversitySelector`; `Contextualizer`; `ExperimentAssigner`; existing retriever/fusion/evaluation ports. Each transformation has schema, deadline, maximum outputs, provenance, and injection-safe prompt construction.

## Security requirements

Transformed queries cannot broaden workspace/ACL scope; untrusted user/retrieved text cannot alter system policy; fan-out/token/cost limits; no hidden query content in logs; experiment isolation; contextualization output validated and linked to source; adversarial query drift/exfiltration tests.

## Failure scenarios

Rewrite changes intent; decomposition omits constraints; multi-query fan-out amplifies cost/latency; duplicate evidence crowds context; contextual text hallucinates facts; one branch fails; configuration drift; improvement comes from leakage; minority slice regresses. Fall back to the Phase 7 baseline under bounded, observable rules.

## Testing strategy

Schema/fan-out/dedup unit tests; intent-preservation and adversarial fixtures; deterministic partial-branch tests; zero-cost offline ablations on overall and slice metrics; paired cost/latency analysis; contextual-citation checks against original spans; rollback and reindex tests; regression gate versus unchanged baseline.

## Acceptance criteria

Every enabled technique has a reproducible ablation showing benefit and tradeoffs; scope and budgets remain invariant; original-query/source provenance is visible; fallback/rollback is tested; rejected techniques are documented with evidence rather than left half-integrated.

## Engineering review focus and implementation drills

Useful implementation drills: bounded multi-query planner; dedup/aggregation; query-drift classifier tests; MMR/diversity selection; contextual-retrieval ablation; architecture recommendation from a Pareto table.

## System-design review focus

Explain which failure slice motivates each technique, why more retrieval can hurt, ingestion-time versus query-time cost, intent drift, fan-out control, LlamaIndex build-versus-buy, experimentation bias, and rollback/migration.

## Explicit deferrals

Do not implement every fashionable technique, autonomous agents, multi-agent routing, self-modifying prompts, or OpenSearch. Techniques without material evidence remain design backlog only. Production experimentation and personalization need explicit requirements.
