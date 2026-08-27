# Phase 2 completion — Source storage and durable asynchronous ingestion

## Implemented scope

Phase 2 adds source/document storage metadata, signed upload intents, digest-verified local object storage, upload finalization, durable ingestion jobs, worker leases, metadata-only publication, status APIs, document deletion, cancellation/retry commands, reconciliation, and workspace UI support.

Implemented modules:

- API application service: `DocumentService`
- API repository implementations: source/upload/document stores and ingestion job store
- API routes: sources, upload intents, signed upload content, finalize, documents, versions, document delete, ingestion job status, cancel, retry
- Object-store boundary: filesystem-backed local adapter with tenant-prefixed keys and HMAC signed URLs
- Worker: deterministic `run-once` ingestion endpoint and non-destructive upload reconciliation endpoint
- Web: workspace source list, document list, upload/finalize form, job status display, delete/cancel/retry controls
- Contract artifacts: regenerated OpenAPI and generated TypeScript API types

## Architecture decisions

Phase 2 keeps PostgreSQL as the authoritative state store. Finalization creates the document, document version, ingestion job, job event, audit event, and idempotency record in one transaction. The worker claims jobs directly from PostgreSQL using `FOR UPDATE SKIP LOCKED`, lease owner, lease expiry, heartbeat, attempts, progress, and expected-version checks.

The local object-store adapter deliberately models the future production boundary but avoids requiring cloud credentials for development and tests. Production S3-compatible storage, bucket policy, encryption, lifecycle rules, and dedicated service identities remain behind the same object-store interface.

## Security properties

- Tenant-owned rows include workspace scope.
- Resource routes require authenticated workspace membership and named permissions.
- Viewer role can read sources/documents/job status but cannot create source or upload state.
- Object keys are server-generated and workspace-prefixed.
- Signed upload URLs are short-lived and bound to upload intent, object key, and expiry.
- Upload receipt validates token, expiry, media type, byte size, and SHA-256 digest.
- Finalization verifies stored object metadata before durable publication work is created.
- Worker publication rejects stale leases and wrong expected versions.
- Corrupt or missing objects fail safely and do not mark versions ready.
- API and worker responses expose safe IDs/status/errors, not uploaded content.

## Failure handling

- Duplicate finalize with the same idempotency key returns the same logical document/version/job.
- Reusing an idempotency key with a different finalize request fails with conflict.
- Invalid signed tokens and digest mismatches fail before finalization.
- Cross-tenant document listing returns a non-disclosing not-found response.
- Stale worker publication is rejected by expected job version.
- Document deletion tombstones the document, removes it from normal reads, deactivates versions, and requests cancellation for nonterminal ingestion jobs.
- Expired upload-intent reconciliation marks stale non-finalized intents and reports orphan or missing objects without destructive deletion.

## Validation evidence

The phase gate includes API lint/typecheck/tests, worker lint/typecheck/tests, web lint/typecheck/build, contract generation, migration execution, and an end-to-end local demonstration through HTTP.

## Explicit deferrals

Phase 2 does not implement production cloud object storage, malware scanning, magic-byte file classification, parser sandboxing, extracted text, chunking, embeddings, retrieval, grounded generation, evaluation datasets, Redis queue transport, external connectors, OCR, document deletion propagation, or production quota ledgers. These remain later-phase work.
