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
| D09 | PostgreSQL is the initial retrieval authority; pgvector is the first indexed-vector candidate once benchmarked in the local stack | Fixed boundary; index choice evidence gate | One authorization/transaction boundary and lower operational burden. Phase 4 ships zero-cost exact cosine search over PostgreSQL-stored normalized vectors because the current default compose image is plain PostgreSQL. pgvector HNSW/IVF adoption requires a deliberate image/extension migration, query-plan evidence, and recall/latency comparison. OpenSearch remains a later benchmarked projection, not assumed. |
| D10 | Hybrid candidate generation with identical policy filters and RRF as the first fusion baseline | Fixed baseline | Semantic and lexical retrieval have complementary failure modes; RRF is robust without score calibration. Learned/weighted fusion requires evaluation evidence. |
| D11 | Retrieval produces typed, versioned `Evidence`; generation consumes only evidence; citations are post-validated | Fixed | Makes grounding testable and prevents model-created source identities from being trusted. |
| D12 | Provider-neutral ports with explicit capabilities, deterministic local fakes for tests/demos, and normalized error taxonomy; external providers are opt-in | Fixed | Supports OpenAI/Anthropic/Bedrock evolution without paid calls in the default path, lowest-common-denominator abstractions, or premature integrations. |
| D13 | Persist model/provider/version, prompt/config, parser/chunker, index, and evaluation provenance | Fixed | Reproducibility, regression diagnosis, and safe migrations require lineage. |
| D14 | OpenAPI is the API contract; TypeScript clients/types are generated or contract-tested | Fixed | Avoids Python/TypeScript drift. Domain models are not shared directly across languages. |
| D15 | Deterministic workflow before agent; LangGraph only for bounded research with durable checkpoints and budgets | Fixed | Most product flows need reliability, not autonomy. Agent behavior must be measurable and interruptible. |
| D16 | No multi-agent runtime unless a named benchmark shows material benefit over a single bounded workflow | Fixed evidence gate | Coordination, context duplication, failure propagation, cost, and evaluation complexity are real. Alternative topologies may be modeled separately, but production runtime complexity requires benchmark evidence. |
| D17 | OpenTelemetry is the base instrumentation with local/no-export defaults; an AI observability sink such as Langfuse is optional behind an adapter | Fixed late-phase integration, schemas early | Avoids vendor lock-in and paid SaaS requirements while preserving AI-specific lineage. Raw sensitive content collection is off by default. |
| D18 | REST/JSON first; cursor pagination; stable error envelope; idempotency keys on replayable commands | Fixed initially | Simple, debuggable contracts. GraphQL/event streaming require a concrete UX or integration need. |
| D19 | Security controls are phase-local and cumulative; retrieved/model/tool content is untrusted | Fixed | A final security pass cannot repair missing tenant/data-flow invariants. |
| D20 | Evaluation gates advanced retrieval, agent complexity, OpenSearch, and optimization changes | Fixed | These choices depend on corpus and workload. Golden-set quality and leakage controls precede tuning. |
| D21 | Phase 1 uses deterministic development auth locally and OIDC/JWKS verification as the production boundary | Fixed | Local tests and demos must not depend on a live identity provider. Production settings reject development auth and require JWKS configuration so unsafe local credentials cannot silently ship. |
| D22 | Workspace creation idempotency is scoped by actor, operation, and key hash, and serialized with a PostgreSQL transaction advisory lock | Fixed initially | This prevents duplicate workspace side effects during retries while keeping the implementation simple. Broader reusable idempotency middleware is deferred until multiple commands need the same abstraction. |
| D23 | Audit events for Phase 1 workspace and membership mutations are transactional with the mutation | Fixed initially | The system prefers fail-closed auditability for administrative control-plane changes. Later high-volume/audit-export flows may add an outbox, but the authoritative audit row remains part of the command transaction unless evidence changes the tradeoff. |
| D24 | Tailwind CSS is the required styling system for the Next.js web app | Fixed | Tailwind gives consistent design tokens, utility composition, and predictable future UI iteration. The Phase 1 dark theme is implemented through Tailwind's PostCSS pipeline and layer model rather than framework-free global CSS. |
| D25 | Phase 2 local development uses an API-hosted filesystem object-store adapter with HMAC-signed upload URLs | Fixed implementation; production adapter deferred | This preserves the object-storage boundary, tenant-prefixed unpredictable keys, digest checks, and short-lived upload semantics without requiring cloud credentials for local tests. S3-compatible storage, bucket policy, server-side encryption, and lifecycle rules are deferred to the deployment phase behind the same adapter interface. |
| D26 | Phase 2 ingestion uses PostgreSQL `FOR UPDATE SKIP LOCKED` leasing and expected-version publication | Fixed initial implementation | A database-backed durable queue avoids dual-write risk and keeps status authoritative. A dedicated broker can be introduced later only after queue-depth, oldest-age, throughput, isolation, or scheduling evidence justifies the operational cost. |
| D27 | Every phase must retain a zero-cost build/test/demo path; billable cloud/SaaS/domain/model integrations are explicit opt-in only | Fixed | The default engineering workflow must be reproducible without monetary spend. Production-grade abstractions remain valuable, but tests and demonstrations use local open-source infrastructure and deterministic fakes unless the user explicitly approves billable execution. |
| D28 | Phase 3 supports deterministic text/Markdown parsing first, with richer converters deferred behind the parser boundary | Fixed initial implementation; format expansion evidence gate | A narrow allowlist keeps the default ingestion path safe, zero-cost, debuggable, and testable while preserving the parser/chunker provenance model. PDF, office, OCR, archive, and semantic/contextual chunking support require sandboxing, fixture coverage, and quality/resource evidence before adoption. |
| D29 | Phase 4 uses deterministic local hash embeddings and exact cosine retrieval as the default product gate | Fixed implementation; provider/index evidence gate | This proves embedding-set provenance, tenant-safe evidence retrieval, batching, dimension checks, and zero-cost demos without paid APIs or large model downloads. Hosted embedding providers and pgvector ANN indexes remain adapter-compatible opt-ins after explicit approval and benchmark evidence. |
| D30 | Phase 5 uses PostgreSQL full-text search plus RRF as the zero-cost hybrid retrieval baseline | Fixed implementation; optimization evidence gate | PostgreSQL FTS keeps lexical search in the existing tenant-filtered authority boundary and avoids a managed search dependency. RRF combines semantic and lexical ranked lists without score calibration, deduplicates chunk/version identity, and records branch ranks/scores for diagnosis. Weighted fusion, query rewriting, synonyms, multilingual analyzers, OpenSearch, and ANN tuning require evaluation evidence. |
| D31 | Phase 6 uses synchronous deterministic local generation with post-generation citation validation as the product gate | Fixed implementation; provider/streaming evidence gate | The zero-cost gate proves answer-run provenance, context budgeting, data/instruction separation, citation allowlisting, and persistence without paid model APIs or large local downloads. Hosted generators, cross-encoder rerankers, streaming, provider fallback, and richer claim-level citation analysis remain behind adapter interfaces and require quality/latency/cost evidence before adoption. |
| D32 | Phase 7 uses deterministic offline evaluation runs over the real retrieval and answer services | Fixed implementation; judge/threshold evidence gate | Evaluation must exercise the production retrieval and answer interfaces rather than copied metric-specific logic, otherwise regressions can be hidden by test-only behavior. The zero-cost gate uses versioned datasets, immutable labels, custom metric oracles, deterministic local metrics, aggregate/slice/failure reports, and append-only baseline approval. Hosted judges, online experimentation, arbitrary regression thresholds, and automated tuning require reviewed baseline distributions plus explicit opt-in because they add cost, privacy, and statistical risk. |
| D33 | Phase 8 enables only one advanced RAG technique by default: deterministic bounded query expansion behind an allowlisted retrieval configuration | Fixed implementation; broader advanced-RAG evidence gate | Phase 7-style ablation showed the named vocabulary-mismatch slice improving from zero recall under baseline lexical retrieval to full recall under `phase8-multi-query-expansion-v1` without paid providers. The configuration is explicit, bounded, observable, reversible, and preserves tenant/resource filters. Contextual retrieval, learned fusion, LlamaIndex components, OpenSearch, and personalization remain deferred until their own ablations prove quality benefit versus added latency, cost, privacy, and failure modes. |

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
- Exact embedding/generation/reranking provider and model: default tests/demos use deterministic local fakes; any paid or hosted provider is opt-in and compared by quality/latency/cost only after approval.
- Vector index type and parameters: require corpus size and recall/latency curves.
- Chunk size/overlap/structure-aware method: Phase 3 ships deterministic text-first defaults; tune future values on evaluation cases, not folklore.
- Weighted fusion, query expansion, contextual retrieval, and reranking depth: enable only with ablations.
- Synchronous versus asynchronous answer API: measure model latency and UX timeout requirements.
- PostgreSQL RLS: add after application policy is testable; benchmark operational implications.
- OpenSearch: require a documented feature/scale trigger and shadow comparison.
- Kubernetes/microservices: not in the current plan; any AWS/ECS/Fargate-style deployment remains optional and must not provision billable infrastructure without explicit approval.
- Multi-region active-active: defer until RTO/RPO, residency, and customer requirements exist.
- Fine-grained document ACLs/connectors: initial workspace-scoped visibility keeps the model correct; expand from explicit product requirements.
