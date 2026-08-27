# Cross-phase architecture decisions

This is the decision ledger. “Fixed” means later phases must not casually revisit it. “Evidence gate” means the interface is fixed now but implementation choice awaits measurements.

| ID | Decision | Status | Rationale and consequences |
|---|---|---|---|
| D01 | pnpm + Turborepo monorepo with web/api/worker and only config/shared-types packages initially | Fixed | Clear deployable boundaries and cross-language coordination without package proliferation. Python services may share a Python workspace/library inside an app until reuse proves a package boundary. |
| D02 | Modular monolith control/query plane plus separate worker process | Fixed initially | Maximizes learnability and transactional clarity. Service decomposition is deferred until ownership, scaling, or failure-isolation evidence exists. |
| D03 | PostgreSQL is authoritative; source blobs use S3-compatible object storage; Redis is non-authoritative | Fixed | Matches data shape and recovery needs; avoids large blobs and correctness state in unsuitable stores. |
| D04 | Tenant scope is explicit in domain inputs, rows, constraints, queries, object keys, cache keys, jobs, and telemetry | Fixed | Defense in depth. PostgreSQL RLS is an additional control considered after repository-level tests, not a substitute for correct application authorization. |
| D05 | Authorization uses workspace roles plus resource visibility policy; policy is centralized in application/domain services | Fixed | Prevents route-only checks and makes worker/system actions auditable. Fine-grained ACL expansion is deferred until requirements demand it. |
| D06 | Ingestion is an idempotent, versioned, at-least-once state machine with durable publication | Fixed | Providers and workers fail. Exactly-once side effects are unrealistic; uniqueness, checkpoints, and atomic publish create effective-once outcomes. |
| D07 | Begin with database-backed job claiming/outbox semantics; hide transport behind a job port | Fixed interface; transport evidence gate | Avoids premature queue infrastructure while preventing dual writes. Adopt a dedicated broker/managed queue when throughput, isolation, delay/retry semantics, or operations justify it. Redis must not be the only durable record. |
| D08 | Immutable document versions, chunks, and embedding sets; publish only complete versions | Fixed | Enables retry, audit, citation stability, rollback, and embedding migrations. Storage overhead is accepted and managed by retention policy. |
| D09 | pgvector is the initial vector engine and PostgreSQL full-text search is the initial lexical engine | Fixed initially | One authorization/transaction boundary and lower operational burden. OpenSearch is a later benchmarked projection, not assumed. |
| D10 | Hybrid candidate generation with identical policy filters and RRF as the first fusion baseline | Fixed baseline | Semantic and lexical retrieval have complementary failure modes; RRF is robust without score calibration. Learned/weighted fusion requires evaluation evidence. |
| D11 | Retrieval produces typed, versioned `Evidence`; generation consumes only evidence; citations are post-validated | Fixed | Makes grounding testable and prevents model-created source identities from being trusted. |
| D12 | Provider-neutral ports with explicit capabilities and normalized error taxonomy; initially integrate one provider per capability | Fixed | Supports OpenAI/Anthropic/Bedrock evolution without lowest-common-denominator abstractions or premature integrations. |
| D13 | Persist model/provider/version, prompt/config, parser/chunker, index, and evaluation provenance | Fixed | Reproducibility, regression diagnosis, and safe migrations require lineage. |
| D14 | OpenAPI is the API contract; TypeScript clients/types are generated or contract-tested | Fixed | Avoids Python/TypeScript drift. Domain models are not shared directly across languages. |
| D15 | Deterministic workflow before agent; LangGraph only for bounded research with durable checkpoints and budgets | Fixed | Most product flows need reliability, not autonomy. Agent behavior must be measurable and interruptible. |
| D16 | No multi-agent runtime unless a named benchmark shows material benefit over a single bounded workflow | Fixed evidence gate | Coordination, context duplication, failure propagation, cost, and evaluation complexity are real. Learn patterns through design exercises first. |
| D17 | OpenTelemetry is the base instrumentation; Langfuse is the AI observability/evaluation view | Fixed late-phase integration, schemas early | Avoids vendor lock-in while providing AI-specific lineage. Raw sensitive content collection is off by default. |
| D18 | REST/JSON first; cursor pagination; stable error envelope; idempotency keys on replayable commands | Fixed initially | Simple, debuggable contracts. GraphQL/event streaming require a concrete UX or integration need. |
| D19 | Security controls are phase-local and cumulative; retrieved/model/tool content is untrusted | Fixed | A final security pass cannot repair missing tenant/data-flow invariants. |
| D20 | Evaluation gates advanced retrieval, agent complexity, OpenSearch, and optimization changes | Fixed | These choices depend on corpus and workload. Golden-set quality and leakage controls precede tuning. |
| D21 | Phase 1 uses deterministic development auth locally and OIDC/JWKS verification as the production boundary | Fixed | Local tests and demos must not depend on a live identity provider. Production settings reject development auth and require JWKS configuration so unsafe local credentials cannot silently ship. |
| D22 | Workspace creation idempotency is scoped by actor, operation, and key hash, and serialized with a PostgreSQL transaction advisory lock | Fixed initially | This prevents duplicate workspace side effects during retries while keeping the implementation simple. Broader reusable idempotency middleware is deferred until multiple commands need the same abstraction. |
| D23 | Audit events for Phase 1 workspace and membership mutations are transactional with the mutation | Fixed initially | The system prefers fail-closed auditability for administrative control-plane changes. Later high-volume/audit-export flows may add an outbox, but the authoritative audit row remains part of the command transaction unless evidence changes the tradeoff. |
| D24 | Tailwind CSS is the required styling system for the Next.js web app | Fixed | Tailwind gives consistent design tokens, utility composition, and predictable future UI iteration. The Phase 1 dark theme is implemented through Tailwind's PostCSS pipeline and layer model rather than framework-free global CSS. |

## Important interfaces

Names are conceptual; exact module paths are chosen in the relevant phase.

```text
IdentityContext(subject_id, workspace_id, roles, authn_strength)
AuthorizationPolicy.require(actor, action, resource)

ObjectStore.create_upload_intent(...), head(...), get_stream(...), put(...)
UnitOfWork.transaction(...)
JobRepository.enqueue(...), claim(lease), heartbeat(...), transition(...), release(...)

Parser.can_parse(media_type), parse(stream) -> ParsedDocument
Chunker.chunk(parsed, config) -> list[ChunkDraft]
EmbeddingProvider.embed(texts, model) -> EmbeddingBatch

SemanticRetriever.search(QuerySpec) -> list[Candidate]
LexicalRetriever.search(QuerySpec) -> list[Candidate]
FusionStrategy.fuse(candidate_lists, limit) -> list[Candidate]
Reranker.rerank(query, candidates) -> list[Candidate]
ContextBuilder.build(query, candidates, budget) -> ContextPackage

Generator.generate(GenerationRequest) -> StructuredAnswer
CitationValidator.validate(answer, ContextPackage) -> CitationReport

EvaluationMetric.compute(case, output) -> MetricResult
ResearchTool.invoke(AuthorizedToolCall) -> SanitizedToolResult
BudgetLedger.reserve/commit/release(...)
```

Every interface carries workspace/resource scope, trace context, timeout/cancellation, and version/config provenance where relevant. Infrastructure errors are normalized into validation, authorization, conflict, transient dependency, permanent dependency, resource exhausted, cancelled, and internal categories.

## Decisions intentionally deferred to benchmarks or evidence

- Queue transport and workflow engine for ingestion: measure durable DB-job limits and operational needs.
- Exact embedding/generation/reranking provider and model: choose an affordable baseline, then compare quality/latency/cost.
- Vector index type and parameters: require corpus size and recall/latency curves.
- Chunk size/overlap/structure-aware method: tune on evaluation cases, not folklore.
- Weighted fusion, query expansion, contextual retrieval, and reranking depth: enable only with ablations.
- Synchronous versus asynchronous answer API: measure model latency and UX timeout requirements.
- PostgreSQL RLS: add after application policy is testable; benchmark operational implications.
- OpenSearch: require a documented feature/scale trigger and shadow comparison.
- Kubernetes/microservices: not in the current plan; ECS/Fargate-style deployment is the simpler AWS baseline unless constraints change.
- Multi-region active-active: defer until RTO/RPO, residency, and customer requirements exist.
- Fine-grained document ACLs/connectors: initial workspace-scoped visibility keeps the model correct; expand from explicit product requirements.
