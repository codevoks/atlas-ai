# Failure model and recovery semantics

## Error taxonomy

All boundaries normalize failures into: invalid input; unauthenticated; unauthorized; not found/non-disclosing; conflict/concurrent change; cancelled; deadline exceeded; transient dependency; permanent dependency/configuration; throttled/resource exhausted; policy rejected; integrity violation; internal defect. Only classified transient/throttled failures retry, with bounded exponential backoff, jitter, deadlines, and retry budgets.

## Failure matrix

| Scenario | Invariant and user-visible outcome | Detection and recovery |
|---|---|---|
| Upload abandoned | No document version is finalized/searchable; orphan bytes expire | Intent expiry/lifecycle plus reconciliation; Phase 2 stores expiry and object key for cleanup |
| Object uploaded, DB finalize fails | Retry finalization by idempotency key or expire object; do not guess ownership | Object metadata/digest and intent reconciliation; Phase 2 verifies object HEAD before transaction |
| DB job created, notification fails | Durable job remains claimable; status shows pending | DB polling/claiming is authoritative in Phase 2; notification is not authority |
| Duplicate job/delivery | One stage/version effect; no duplicate publication/spend beyond bounded unavoidable provider retry | Unique effect keys, expected transitions, stage checkpoints; Phase 2 uses unique job keys and versioned leases |
| Worker crash/stall | Lease expires; another worker resumes from safe checkpoint | Heartbeat/lease monitor, stale-owner rejection; Phase 2 rejects stale publication by expected job version |
| Parser malicious/crash/OOM | Version quarantined/failed, worker pool survives, no searchable chunks publish | Phase 3 allowlisted text parser rejects binary/PDF/archive/invalid UTF-8 and enforces byte/chunk limits; later sandboxed converters add process/container isolation |
| Embedding partial batch | Version remains unpublished; completed items retained by set; retry missing/failed | Coverage query, per-item status/upsert, bounded backoff |
| Redis unavailable | Authoritative data/status survives; queues/cache/rates degrade safely | Health/saturation alert, DB job fallback/pause, cache rebuild |
| PostgreSQL unavailable | Authz/state-changing/search operations fail safely; no alternate authority | Timeouts/circuit control, HA/restore runbook, no blind retries |
| Object missing/corrupt | Version never publishes or becomes integrity-failed; existing published version remains | HEAD/digest verification, restore/reupload/reprocess |
| Semantic/lexical branch timeout | Policy-safe partial evidence may be labeled if product mode allows | Per-branch deadline, diagnostics, no relaxed filters |
| Reranker unavailable | Use recorded baseline order if within quality policy, or fail visibly | Circuit state and fallback metric/alert |
| Generator unavailable/malformed | Evidence-only or explicit failure; never fabricate answer/citation | Schema validation, bounded provider retry/fallback policy |
| Citation mismatch | Citation rejected/unverified; answer policy decides partial display/refusal | Evidence allowlist and ID/span/claim validation |
| Membership revoked mid-run | New privileged step/read fails fresh authorization; cached results cannot grant access | Short cache/session policy, checks at use-case/tool/approval boundaries |
| Research crash after tool effect | Resume must not repeat non-idempotent effect silently | Invocation key, effect receipt, checkpoint/outbox, approval/reconciliation |
| Infinite/expensive agent | Hard termination and budget terminal state | Atomic reservations, counters, deadline/step/tool caps |
| Telemetry exporter down | Core path continues within bounded buffer/drop; no memory/disk cascade | Exporter health/drop metric and backpressure policy |
| Derived OpenSearch lag | PostgreSQL truth prevents unauthorized/deleted results; freshness is visible | Cursor/tombstone/reconciliation, shadow/fallback, rebuild |
| Bad migration/deploy | Old/new versions coexist during expand/contract; rollback does not corrupt | Compatibility tests, protected rollout, backup/restore/reindex plan |
| Missing internal operations token | Internal metrics stay unavailable; production configuration refuses to start | Configure `OPS_INTERNAL_TOKEN` through the deployment secret manager and verify `/internal/ops/metrics` with the token |
| Billable provisioning attempted from default path | No cloud resources are created by repository defaults | Phase 11 artifact validation rejects CI Terraform apply, AWS credentials in CI, and Terraform resource blocks |

## Retry and timeout rules

Deadlines shrink across nested calls; a child cannot outlive its request/job budget unless explicitly detached as a durable job. Avoid multiplicative retries across HTTP client, adapter, job, and workflow layers: one owner controls retries for an effect. Honor provider `Retry-After`, cap attempts and elapsed time, and use circuit/load shedding when recovery is unlikely. Permanent validation/auth/policy/integrity failures never retry automatically.

## Safe degradation

Fail closed for identity, authorization, tenant ambiguity, active-version publication, approval, budget reservation, and claims of verified citations. Possible labeled degradation includes lexical-only/semantic-only search, baseline order without reranker, evidence without generation, deferred telemetry, and paused ingestion. Degradation never expands data/tool scope or hides integrity uncertainty.

## Recovery evidence

Each phase adds crash-point tests and an operator-visible repair path. Production hardening proves PostgreSQL restore, object recovery/versioning policy, derived-index rebuild, migration rollback/forward-fix, job reconciliation, checkpoint resume, secret rotation, and deletion propagation. A backup is not a recovery capability until restored and timed.

Phase 4 recovery evidence covers deterministic parser/chunker/embedding tests, corrupt/binary/unsupported input failure tests, parser byte-limit enforcement, chunk-count enforcement, embedding dimension/normalization checks, semantic-search bounds checks, and integration coverage that published chunks/embeddings remain tenant-scoped and are written only with ready document-version metadata.

Phase 11 recovery evidence covers readiness behavior, protected operations metrics, content-off
telemetry, local SLO observation, no-billable Terraform defaults, CI validation structure, and
container build specifications. Real cloud restore, remote-state recovery, registry signing, and
production rollback drills remain deployment-specific work until an approved account/environment
exists.
