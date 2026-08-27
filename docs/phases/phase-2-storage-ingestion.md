# Phase 2 — Source storage and durable asynchronous ingestion

## Scope

Implement source/document/version metadata, direct-to-object-store upload intents and finalization, durable ingestion jobs, worker leasing/heartbeat/retry/cancel/replay, transactional publication mechanism, status UI/API, and cleanup/reconciliation. Stages may verify and hand off placeholder processing; parsing/chunking belongs to Phase 3. The implementation and demonstration must remain zero-cost: local PostgreSQL, local filesystem object storage, deterministic development authentication, and local API/web/worker services only.

## Engineering concepts

Blob versus relational storage, presigned uploads, content addressing, state machines, at-least-once delivery, idempotency, transactional outbox/database job queue, leases, heartbeats, backoff/jitter, dead letters, cancellation, optimistic concurrency, eventual consistency, reconciliation.

## Architecture changes and modules

Add object-store adapter, source/document application modules, job repository/scheduler/consumer, worker execution shell, and reconciliation commands. API owns upload authorization/finalization; worker reads immutable authoritative job state. Transport remains behind the job port.

## Data model changes

Add `sources`, `documents`, `document_versions`, `ingestion_jobs`, optional `job_events/outbox`. Version fields include tenant, digest, server-generated object key, media type, size, status, active flag, requested pipeline config. Job fields include stable idempotency key, stage/state, attempts, lease owner/expiry, heartbeat, progress, error class/code, cancellation request, next-attempt time. Constraints prevent two active publications and duplicate command effects.

## APIs

Create/list sources; request upload intent; finalize upload; list/get/delete documents and versions; get job status; cancel; admin retry/reprocess. Finalize verifies object head/digest/limits and atomically creates version + job visibility. `202` responses link status resources. Retry is a new authorized command with explicit semantics, not blind status mutation.

## Important interfaces

`ObjectStore` streaming/head/signed-upload/delete; `JobRepository.enqueue/claim/heartbeat/transition/release`; `IngestionStage.execute(context)`; `RetryClassifier`; `BackoffPolicy`; `Reconciler`; `Clock`; `CancellationToken`. Transitions use expected state/version and write safe events.

## Security requirements

Tenant-prefixed unpredictable keys, short-lived scoped URLs, private bucket, encryption, checksum and magic-byte/size verification, immutable/quarantine state, no client-chosen path, service identities separated, job payload distrust, authorization on status/retry/delete, per-tenant upload/queue quotas, metadata/log redaction, lifecycle/deletion audit.

## Failure scenarios

Upload abandoned; finalize repeated; object exists but DB commit fails; DB commit succeeds but notifier fails; duplicate delivery; worker dies before/after effect; stale lease overwrites progress; object missing/corrupt; Redis/broker unavailable; poison job; cancellation during external call; deletion races ingestion. Reconciliation must find orphans and stuck jobs without destructive guesses.

## Testing strategy

State-transition property/table tests; integration tests for transactional enqueue and object adapter; crash-point/fault-injection tests around every boundary; duplicate/reorder/stale-lease tests; cancellation and retry classification; cross-tenant signed URL/status tests; zero-cost local small-object end-to-end; migration, lint, typecheck, build.

## Acceptance criteria

Accepted uploads are never silently lost; duplicate finalize/delivery produces one logical version/job effect; progress is authoritative and diagnosable; stale workers cannot publish; terminal failures are safe/replayable; object/DB orphans are detectable; quotas and authorization hold; Phase 3 has a stable stage contract.

## Engineering review focus and implementation drills

Design and defend an at-least-once state machine. Useful implementation drills: transition reducer; idempotency-key repository; lease/heartbeat race test; retry classifier/backoff; repair a DB+queue dual write; build an orphan reconciliation algorithm.

## System-design review focus

Explain async ingestion, why S3 not PostgreSQL blobs, effective-once versus exactly-once, queue backpressure, lease safety, consistency seen by users, retry storms, tenant fairness, object retention/deletion, and queue transport migration.

## Explicit deferrals

No production parsers/chunkers/embeddings/retrieval. Malware scanning implementation and dedicated queue selection may be deferred behind enforceable quarantine/adapter boundaries until deployment constraints are known. Connectors and OCR remain later backlog, not silent scope.
