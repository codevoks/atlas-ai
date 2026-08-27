# Threat model and security requirements

## Security objectives

Atlas must prevent cross-tenant access, unauthorized actions, unsafe file processing, secret leakage, prompt/tool authority escalation, citation deception, abuse-driven cost, and silent loss/corruption. Availability and bounded spend are security properties. Model output is never trusted merely because it is structured.

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
| Dependencies/CI/CD | supply-chain compromise, secret exposure, artifact tampering | lockfiles, provenance/scanning, minimal permissions, pinned actions, OIDC to cloud, protected environments, signed/scanned images |

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

- PostgreSQL-backed integration tests and migration execution are written but could not be completed in the current environment because no local PostgreSQL service is running.
- Rate limiting for auth/admin operations is still deferred; add before public exposure.
- PostgreSQL RLS remains a later defense-in-depth decision after repository policy tests are proven.
- Local development auth must never be exposed beyond local development; production deployments must use real OIDC/JWKS secrets and environment validation.
