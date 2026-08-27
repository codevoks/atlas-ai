# Threat model and security requirements

## Security objectives

Atlas must prevent cross-tenant access, unauthorized actions, unsafe file processing, secret leakage, prompt/tool authority escalation, citation deception, abuse-driven cost, and silent loss/corruption. Availability, bounded spend, and a zero-cost default build/test/demo path are security and operability properties. Model output is never trusted merely because it is structured.

## Assets and actors

Assets: source files and extracted text, embeddings, identities/memberships, workspace policy, answers/citations, API/provider credentials, job and research state, evaluation data, audit trails, billing/budget state, and infrastructure configuration.

Actors: anonymous internet client, authenticated member, workspace admin/owner, internal service identity, operator, compromised account, malicious tenant, malicious uploaded document/source, compromised dependency/provider, and accidental developer/operator.

## Boundaries and principal threats

| Boundary | Threats | Required controls |
|---|---|---|
| Browser → web/API | session theft, CSRF, XSS, forged workspace IDs, IDOR, mass assignment, abuse | secure cookie/session/OIDC validation, CSRF protection where cookie-authenticated, strict schemas, server-derived tenant context, output encoding/CSP, rate limits, generic errors |
| API/worker → database | missing tenant predicate, injection, overprivileged role, unsafe migration | parameterized access, repository policy tests, least-privilege identities, tenant-aware constraints, reviewed migrations, optional RLS defense |
| Client/API → object store | key guessing, content-type spoofing, oversized uploads, overwrite, malware | short-lived scoped signed URLs, server-generated keys, checksum/size/type verification, immutable objects, quarantine/scanning policy, no public bucket |
| Job publisher → worker | duplicate/forged jobs, stale lease, poison message, replay | durable authoritative job record, signed/service-authenticated transport, idempotency keys, leases/heartbeats, max attempts, dead-letter state, tenant scope |
| Parser/converter | parser exploit, archive bomb, path traversal, memory/CPU exhaustion | allowlisted types, magic-byte validation, stream/size/page/time limits, isolated process/container, patched parsers, no outbound network, safe temp paths |
| Retrieval | cross-tenant candidates, poisoned content, filter mismatch, stale/deleted content | filters applied inside every branch, published-version predicate, authorization tests, provenance/trust labels, deletion/tombstone propagation |
| Retrieved context → model | indirect prompt injection, exfiltration, instruction collision, sensitive-data disclosure | data/instruction separation, delimiters/labels, context minimization, policy filters, no secrets in prompts, provider data controls, canary/adversarial tests |
| Model → application/user | fabricated citation, unsafe content, schema confusion, UI injection | schema validation, evidence allowlist, citation/span validation, policy validation, safe rendering, refusal/degraded state |
| Model → tool | arbitrary tool use, confused deputy, SSRF, exfiltration, destructive action | structured allowlisted tools, per-tool auth scopes, URL/network egress policy, argument validation, budgets/timeouts, output sanitization, human approval |
| Telemetry/export | prompt/document/secret/PII leakage, cross-tenant dashboards | redaction, content-off default, tenant-safe attributes, access controls, retention/deletion policy, sampling, no credentials |
| Dependencies/CI/CD | supply-chain compromise, secret exposure, artifact tampering, accidental billable provisioning | lockfiles, provenance/scanning, minimal permissions, pinned actions, opt-in cloud OIDC only, protected environments, signed/scanned images, no default paid-resource creation |

## Authorization and tenant isolation model

Authentication establishes a subject. Workspace selection is resolved against active membership. Application use cases authorize an action against a typed resource before access. Persistence methods require workspace scope and include it in queries and composite relationships. Workers obtain tenant scope from an authorized, immutable job record, never message payload alone. Object keys, caches, indexes, traces, quotas, and audit events are tenant-scoped.

Initial roles are `owner`, `admin`, `member`, and optionally `viewer`. Permissions are named actions, not route names. Owners cannot be silently removed if that leaves no owner. Membership/role mutations are transactional and audited. Service principals have narrower capabilities than admins.

## AI-specific policy

- System/developer policy outranks user input; retrieved and tool content contains no executable authority.
- Tools expose the minimum necessary operation and data. General shell, arbitrary HTTP, and arbitrary SQL are not research tools.
- Retrieval evidence includes provenance and trust classification. Untrusted sources cannot request tool calls or disclosure.
- Generation receives the least context necessary and no infrastructure/provider credentials.
- Deterministic validation wraps model-assisted classifiers; model safety decisions alone are insufficient for access control.
- Research budgets cap steps, parallelism, model tokens, tool calls, wall time, and money. Reservations are concurrency-safe.
- Default tests and demos use deterministic local provider fakes. Paid model APIs, hosted tools, managed observability, cloud infrastructure, and domains are explicit opt-in only and must not execute or provision during ordinary validation.
- Sensitive or externally consequential actions require explicit human approval and a fresh authorization check.

## Security testing matrix

Every phase adds tests at its boundary. Cumulative suites cover:

- Cross-workspace ID substitution for every tenant resource and retrieval branch.
- Role downgrade/revocation, stale sessions, invitation abuse, and ownership invariants.
- SQL/metadata/filter injection, schema overposting, pagination/rate-limit edge cases.
- Oversized/polyglot/corrupt/archive-bomb uploads, parser timeouts, duplicate jobs, stale workers.
- Malicious chunks asking the model to reveal secrets, ignore policy, invent citations, or call tools.
- Citation IDs/spans not in evidence, poisoned ranking metadata, deleted/stale document visibility.
- SSRF/private-network URLs, redirect chains, tool-argument smuggling, oversized tool output.
- Budget races, retry amplification, denial-of-wallet, tenant starvation, cancellation gaps.
- Log/trace snapshots asserting secret/content redaction.

## Incident-safe failure rules

Fail closed for authentication, authorization, tenant ambiguity, policy validation, citation integrity claims, approvals, and budget reservation. Fail visibly but recoverably for ingestion/provider failures. Search may return partial branch results only when labeled and policy-safe. Never retry permanent validation/auth failures. Quarantine suspicious uploads, revoke exposed credentials, preserve safe audit evidence, and make derived indexes rebuildable.

## Phase review checklist

At each phase update assets/data flows, enumerate new input/output boundaries, define abuse limits, add authorization and negative tests, review secrets/logs/dependencies, document residual risk, and verify secrets plus private/personal material remain outside Git. Phase 10 performs adversarial consolidation; it does not postpone these obligations.

## Phase 1 implementation security review

Implemented controls:

- Development authentication is deterministic and local-only; production settings reject `AUTH_MODE=development`.
- Production authentication is represented by an OIDC/JWKS verifier boundary with issuer, audience, expiry, subject, and email claim validation.
- Current actor resolution is centralized in the API dependency layer.
- Workspace access is derived from active membership and returns non-disclosing `404` when membership is absent.
- RBAC permissions are named domain actions, checked in use cases before repository mutations.
- Workspace/member mutations write audit events in the same transaction.
- Replayable workspace creation requires `Idempotency-Key` and stores request/response hashes.
- Last-owner downgrade/removal is rejected by transactional use-case/repository logic.
- Web requests pass through a BFF API client and avoid browser-side direct API authority decisions.
- Web security headers include CSP, frame denial, content-type nosniff, referrer policy, and restrictive permissions policy.

Residual risks and follow-ups:

- PostgreSQL-backed integration tests and migration execution are part of the phase gate.
- Rate limiting for auth/admin operations is still deferred; add before public exposure.
- PostgreSQL RLS remains a later defense-in-depth decision after repository policy tests are proven.
- Local development auth must never be exposed beyond local development; production deployments must use real OIDC/JWKS secrets and environment validation.

## Phase 2 implementation security review

Implemented controls:

- Source, upload-intent, document, version, ingestion-job, and job-event rows are workspace-scoped.
- Source/document/job APIs authorize against active workspace membership before access.
- Browser-supplied workspace IDs never grant authority; the API checks membership and permission for every Phase 2 resource route.
- Upload object keys are generated server-side with a workspace prefix and upload-intent UUID; clients cannot choose storage paths.
- Local development upload URLs are HMAC signed and expire with the upload intent.
- Upload receipt validates signed token, expiry, media type, byte size, and SHA-256 digest before marking an intent uploaded.
- Finalization verifies stored object metadata and digest before creating document/version/job state.
- Upload finalization is idempotent by actor, operation, idempotency key, and request hash.
- Worker publication requires a valid lease owner and expected job version; stale workers cannot publish.
- Worker failures for missing or corrupt objects terminate as integrity failures and do not publish the version.
- Job cancellation and retry commands are authorized and audited.
- Logs and API responses expose IDs/status/errors but not uploaded content bytes.

Residual risks and follow-ups:

- The Phase 2 object store is a local filesystem adapter for deterministic zero-cost development and demonstration. Production may configure a private S3-compatible bucket, server-side encryption, lifecycle cleanup, and least-privilege service identities behind the same interface only through an explicit deployment path.
- Magic-byte validation, malware scanning, parser sandboxing, archive-bomb controls, extracted text handling, chunking, embeddings, and retrieval authorization are deferred to later ingestion/retrieval phases.
- Per-tenant upload quotas and rate limits are represented by size limits and permission checks in Phase 2 but still need durable quota ledgers before public exposure.
- Automated orphan cleanup/reconciliation is designed but not scheduled in Phase 2; implementation belongs with production object-storage lifecycle or a dedicated maintenance worker.

## Phase 3 implementation security review

Implemented controls:

- Parsing is allowlisted to deterministic text and Markdown-like inputs for the zero-cost path.
- Binary magic bytes, PDFs, archives, OLE containers, PNG files, null bytes, invalid UTF-8, empty extracted text, oversized parser input, and excessive chunk output fail safely.
- Parser and chunker names/versions, normalized artifact key/digest, counts, and safe metadata are persisted with the immutable document version.
- Normalized derived artifacts are written under workspace-prefixed object keys and verified by SHA-256 digest.
- Chunk rows are workspace-scoped, tied to one immutable document version, ordered deterministically, and published in the same transaction as ready version state.
- Chunk preview APIs require active workspace membership and document-read permission; cross-tenant chunk lookups return non-disclosing `404`.
- The web UI renders chunk text as escaped React text and does not treat extracted content as HTML or instructions.
- Parser failures classify jobs as failed with safe error codes/messages and do not expose uploaded bytes or extracted content in logs/API errors.

Residual risks and follow-ups:

- The Phase 3 parser is intentionally narrow. PDF, office formats, OCR, archives, HTML sanitization, malware scanning, and sandboxed third-party converters remain deferred until their dedicated phases or evidence-backed demand.
- The current text parser runs in-process because it handles only bounded UTF-8 text. Any richer converter must run behind the parser-sandbox boundary with CPU, memory, file-system, temp-path, and network controls.
- Chunk text is stored directly in PostgreSQL for the initial retrieval path. Encryption, redaction policy, retention controls, and large-document storage optimization remain deployment/security hardening work.
- Chunk quality parameters are deterministic defaults, not final retrieval-tuned values. Later evaluation phases must benchmark chunk size, overlap, and structure preservation before changing defaults.

## Phase 4 implementation security review

Implemented controls:

- Document publication now requires complete embeddings for the configured active embedding set before a version is marked `READY`.
- Embedding sets persist provider, model, model version, dimension, normalization, configuration, lifecycle status, and workspace scope. Vectors from different sets are not compared.
- The default embedding provider is deterministic and local. It does not call paid APIs, hosted providers, or mandatory local LLM downloads.
- Semantic retrieval checks active workspace membership and `document:read` permission before search.
- Tenant, active-document, active-version, ready-version, embedding-set, and optional metadata filters are applied before ranking candidates.
- Search responses return typed evidence, snippets, scores, distances, IDs, trace ID, and bounded debug metadata. They do not expose raw vectors.
- Query length and `top_k` are bounded, and empty/non-token queries fail safely.

Residual risks and deferrals:

- Phase 4 uses an exact PostgreSQL JSONB vector baseline for the zero-cost path. pgvector ANN index adoption is deferred until the local stack deliberately includes the extension and query-plan/recall/latency evidence justifies it.
- Embedding inversion/linkability remains a privacy risk. Raw vector export, tenant analytics, retention policy, and provider data-retention policy require later dedicated controls before hosted providers are enabled.
- Search is semantic-only evidence retrieval. Lexical/hybrid retrieval, reranking, grounded generation, citation validation, and adversarial prompt-injection evaluation remain deferred to later phases.

## Phase 5 implementation security review

Implemented controls:

- The unified search endpoint authorizes `document:read` against active workspace membership before candidate generation.
- Semantic and lexical branches both apply workspace, active-document, ready-active-version, and allowlisted source/document filters before ranking candidates.
- PostgreSQL lexical search uses parameterized `websearch_to_tsquery` and a fixed allowlisted language configuration.
- Hybrid search deduplicates by chunk plus document-version identity and never relaxes a branch policy during fusion.
- Search diagnostics are bounded and redacted: they expose mode, config version, branch counts/status, ranks/scores, and provider/config provenance, but they do not persist or echo full user queries.
- Special-character lexical queries are handled safely, and invalid bounds/modes fail through the typed request schema.
- The zero-cost path uses local PostgreSQL FTS, deterministic embeddings, and no paid SaaS, cloud, hosted search, or model API calls.

Residual risks and deferrals:

- Phase 5 executes semantic and lexical retrieval in the existing API transaction path. True branch timeouts, cancellation propagation, and parallel orchestration are represented by interfaces/configuration but require additional infrastructure before high-latency providers are enabled.
- PostgreSQL FTS uses an English analyzer only. Multilingual analyzers, synonyms, phrase tuning, entity-aware search, OpenSearch, caching, and learned/weighted fusion remain deferred until evaluated.
- Retrieval debug metadata is safe for local development, but any production debug access should be role-gated and retention-controlled before exposing tenant-admin diagnostics broadly.
