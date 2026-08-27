# Logical data and state model

This is implementation guidance, not executable schema. Phase owners translate it into migrations without weakening tenant keys, immutability, provenance, or state transitions.

## Conventions and relationships

- Opaque UUID primary keys; UTC timestamps; normalized enums/check constraints; explicit created/updated actors where relevant.
- Every tenant-owned row includes `workspace_id`. Prefer composite candidate keys `(workspace_id, id)` and composite foreign keys so a child cannot reference another workspace accidentally.
- Soft deletion/tombstones are used where asynchronous projections and audit require propagation; hard deletion follows retention policy and auditable purge jobs.
- Immutable versions/configurations are inserted, not edited. Mutable commands use optimistic version columns where races matter.
- Large blobs live in object storage; a database row stores tenant-scoped key, content digest, size, media type, encryption/version metadata, and lifecycle status.

```text
User --< Membership >-- Workspace
Workspace --< Source --< Document --< DocumentVersion
DocumentVersion --< Chunk --< ChunkEmbedding >-- EmbeddingSet
DocumentVersion --< IngestionJob --< JobEvent

Workspace --< AnswerRun --< AnswerEvidence >-- Chunk
AnswerRun --< Citation

Workspace --< EvaluationDataset --< DatasetVersion --< EvaluationCase
DatasetVersion --< EvaluationRun --< EvaluationResult

Workspace --< ResearchRun --< ResearchStep --< ToolInvocation
ResearchRun --< Checkpoint
ResearchRun --< Approval

Workspace --< AuditEvent
```

## Core invariants

### Identity and workspace

- Identity-provider subject is unique within issuer.
- One active membership exists per user/workspace; a user cannot infer an unjoined workspace.
- Each active workspace has at least one active owner. Last-owner removal/role downgrade is transactionally rejected.
- Permission names are stable actions; role membership is data, policy evaluation is application logic.

### Sources and documents

- `Source` is a logical origin/configuration; `Document` is stable identity; `DocumentVersion` is immutable content.
- `(workspace_id, object_key)` and the content digest/version relation are unique according to the chosen dedup policy.
- At most one version per document is active/published. A version can be published only after all configured mandatory stages succeed.
- Deletion prevents new reads immediately from the source of truth and propagates tombstones to derived indexes/caches asynchronously.

Phase 5 implemented tables and indexes:

- `sources`: workspace-scoped upload source registry with active/disabled state.
- `upload_intents`: tenant-prefixed object key, creator, declared filename, media type, byte size, digest, expiry, lifecycle status, and finalized document-version reference.
- `documents`: logical workspace document identity tied to a source and creator.
- `document_versions`: immutable object reference, digest, media type, size, version number, active flag, parser/chunker names and versions, normalized artifact key/digest, aggregate chunk/character/token counts, embedding-set coverage, safe metadata, and ingestion status.
- `ingestion_jobs`: durable ingestion state, lease owner/expiry, heartbeat, progress, bounded attempts, cancellation flag, idempotency key, retry timing, and safe error fields.
- `job_events`: append-only safe state-transition history.
- `chunks`: immutable deterministic chunk rows scoped by workspace and document version, ordered by ordinal, with structural coordinates, token counts, content hashes, text, and safe metadata.
- `embedding_sets`: workspace-scoped provider/model/version/dimension/normalization/config lifecycle rows for vector-space provenance and migration.
- `chunk_embeddings`: one normalized vector per `(chunk_id, embedding_set_id)` with status and token count. Phase 4 stores vectors as PostgreSQL JSONB for the zero-cost exact-cosine baseline; pgvector ANN indexes remain an evidence-gated migration.
- `ix_chunks_fts_english`: a PostgreSQL GIN expression index on `to_tsvector('english', chunks.text)` for the zero-cost lexical retrieval baseline. It is a derived access path over already-authorized chunk text, not a new authoritative data store.

### Jobs

Initial ingestion states:

```text
PENDING -> CLAIMED -> VERIFYING -> PARSING -> NORMALIZING -> CHUNKING
        -> EMBEDDING -> PUBLISHING -> SUCCEEDED

Any active state -> RETRY_WAIT -> CLAIMED
Any nonterminal state -> CANCEL_REQUESTED -> CANCELLED
Any active state -> FAILED
```

Transitions require expected state/version and a valid lease when worker-owned. `attempts`, stage attempts, `next_attempt_at`, lease owner/expiry, heartbeat, progress, safe error class/code, and cancellation are authoritative. A stable command/idempotency key has one logical result. Retry exhaustion produces a terminal diagnosable state; replay is a new audited command or controlled reset with clear lineage.

The durable record and its outbox/job visibility are created in one database transaction. If a transport is later introduced, delivery is a hint to claim authoritative work, not the work itself.

Phase 4 implements this prefix of the full retrieval-ingestion state machine:

```text
PENDING -> CLAIMED -> VERIFYING -> PARSING -> NORMALIZING -> CHUNKING
        -> EMBEDDING -> PUBLISHING -> SUCCEEDED
PENDING|CLAIMED -> CANCEL_REQUESTED -> CANCELLED
VERIFYING|PARSING|CHUNKING|EMBEDDING -> FAILED
FAILED|RETRY_WAIT -> PENDING by authorized retry
```

Reranking, generation, and finer stage-level checkpoints are intentionally deferred until later retrieval phases.

### Chunks and embeddings

- A chunk belongs to exactly one immutable document version and chunker/config version; ordinal and source span are deterministic.
- Chunk text/metadata has bounds and a content hash. Duplicate processing upserts or detects the same deterministic identity.
- An embedding belongs to one chunk and one embedding set. Set defines provider/model/version/dimension/normalization/config.
- Vectors from different embedding sets are never compared. Multiple sets coexist during migration; promotion is atomic after coverage/evaluation.

### Evidence, answers, and citations

- Candidate/evidence identity is `(workspace_id, chunk_id, document_version_id)` plus retrieval configuration/stage provenance.
- `AnswerEvidence` freezes the exact authorized context and ranks/scores supplied to generation.
- A citation points to an answer claim/span and an `AnswerEvidence` item plus exact source span/quote. Validation status distinguishes resolvable, span-matched, supported, and rejected; these are not synonyms.
- An answer is never marked citation-verified if any claimed evidence identity was not supplied and authorized.

### Evaluation

- Dataset versions and cases are immutable after use. A run pins dataset version, code revision, corpus/index snapshot or document-version set, retrieval/prompt/model configs, metric versions, and random seed where applicable.
- Per-case results distinguish system output, metric output, metric failure, and human review. Aggregate scores never replace slice/failure inspection.

### Research and budgets

Research states include `PENDING`, `RUNNING`, `WAITING_APPROVAL`, `PAUSED`, and terminal `SUCCEEDED|FAILED|CANCELLED|BUDGET_EXHAUSTED|TIMED_OUT`. State transitions use optimistic concurrency.

Every step/tool call has stable identity, inputs/config provenance, attempt/status, deadlines, sanitized output/evidence, usage, and terminal reason. Checkpoints are schema-versioned and written atomically with step progress when possible. Budget reservations prevent concurrent overspend: reserve before work, commit actual usage, release unused reservation; expired reservations reconcile.

## Indexes and access paths

Start from observed queries, but plan indexes for active membership lookup; workspace-scoped lists with cursor; document/source identity and active version; claimable jobs by state/next-attempt plus lease expiry; chunks by version/ordinal; embeddings by set/vector plus workspace/published filter path; lexical search vector; answer/research status; evaluation run/case; audit by workspace/time.

Every repository query starts with workspace scope. Global operator queries use a distinct privileged interface and audit path, never an optional `workspace_id = null` convention.

## Migration rules

Use expand/migrate/contract for deployed schemas. Backfills are bounded, resumable jobs. New parser/chunker/embedding/search configurations create parallel versioned data. Promote after coverage and evaluation; retain rollback until expiry criteria. Derived projections expose reconciliation cursor/count/checksum or sampled consistency evidence.
