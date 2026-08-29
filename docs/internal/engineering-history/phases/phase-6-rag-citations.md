# Phase 6 — Reranking, context construction, RAG, and citation integrity

## Scope

Add optional reranking, deterministic context construction, provider-neutral structured generation, evidence-bound citations, post-generation validation, answer-run provenance, streaming decision, safe refusal/degradation, and grounded-answer UI.

## Engineering concepts

Cross-encoder/LLM reranking, candidate depth, context budgets, dedup/diversity, lost-in-the-middle, prompt/data separation, grounded generation, structured outputs, hallucination taxonomy, claim/evidence/citation alignment, streaming tradeoffs, latency/cost budgeting.

## Architecture changes and modules

Add reranker adapter, context builder, prompt/config registry, generator adapter with deterministic local fake as the default test/demo implementation, answer orchestrator, output policy/schema validator, citation validator, answer-run repository, and safe renderer. Retrieval and generation remain separable so each can be evaluated independently.

## Data model changes

Add `answer_runs`, `answer_evidence`, `citations` with workspace/user, query/config/model/prompt versions, immutable chunk/version references, stage scores/ranks, context ordering, token/cost/latency, output/status/policy outcomes, citation answer-span and evidence-span validation. Apply retention/redaction rules to query/answer content.

## APIs

`POST /v1/answers` with query/filters/config returns answer or `202` if measured latency requires async; `GET /v1/answer-runs/{id}`; cancellation if async. Response schema separates text, citations, grounding/validation state, warnings, and request ID. Only evidence IDs from context are legal citations.

## Important interfaces

`Reranker.rerank`; `ContextBuilder.build -> ContextPackage`; `PromptRenderer` with trusted templates and untrusted evidence slots; `Generator.generate -> StructuredAnswer`; `OutputPolicy`; `CitationValidator`; `AnswerOrchestrator`; `UsageMeter`. Every call carries deadline/cancellation/budget/provenance.

## Security requirements

Retrieved text explicitly untrusted; context minimization; no secrets/tools in basic RAG; schema and size enforcement; malicious instruction canaries; citation allowlist/span verification; safe Markdown/URL rendering; provider privacy settings for any external provider; rate/token/cost limits; authorization rechecked before evidence use; sensitive output policy; content-off telemetry default. Paid generation/reranking APIs and large local model downloads are not required for tests or demos.

## Failure scenarios

Reranker timeout or reordered wrong IDs; context exceeds budget; contradictory sources; lost-in-the-middle; generator timeout/rate limit; malformed schema; answer cites absent/deleted/wrong-tenant evidence; streaming emits unsafe partial content; provider succeeds but persistence fails; revocation during a long request. Define labeled fallback: skip rerank, shorten context, evidence-only response, or fail closed depending on invariant.

## Testing strategy

Deterministic adapters and golden context ordering; token-budget/property tests; citation ID/span mutation tests; prompt-injection fixtures; malformed/oversized model output; provider timeout/fallback; cross-tenant evidence attempts; rendering XSS tests; groundedness/faithfulness sample review; latency/cost instrumentation assertions; zero-cost end-to-end answer with source opening.

## Acceptance criteria

Every displayed citation resolves to the exact authorized immutable source span; invalid citations are removed/flagged and never represented as verified; answer provenance is reproducible; provider failures degrade safely; retrieval can be tested without generation; the baseline report records quality/latency/cost from deterministic local execution.

## Engineering review focus and implementation drills

Useful implementation drills: candidate reranking adapter; token-budgeted context builder; lost-in-the-middle reordering; citation validator; debug fabricated citation; implement schema/fallback handling and tests.

## System-design review focus

Explain why reranking helps, context selection tradeoffs, hallucination sources, citations versus groundedness, streaming safety, model/provider abstraction, failure/cost fan-out, and why prompts cannot enforce authorization.

## Explicit deferrals

No query rewriting/contextual retrieval/agent tools. Reranker model/depth, context ordering, streaming, caching, fallback provider, and citation claim-level sophistication remain benchmark/product decisions. Ragas does not replace deterministic checks.
