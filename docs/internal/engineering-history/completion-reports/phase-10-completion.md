# Phase 10 completion — AI security, guardrails, and adversarial assurance

## Scope completed

Phase 10 adds deterministic local security guardrails and executable assurance evidence across high-risk AI SaaS boundaries:

- Central guardrail primitives for input scanning, output scanning, redaction, and egress policy.
- Admin-only security posture and security event APIs.
- Redacted persisted security events for guardrail detections and quota abuse.
- PostgreSQL fixed-window quota counters for search, answer, and research operations.
- Data-model foundations for versioned policy configs, content trust/quarantine state, and retention tombstones.
- Workspace UI visibility for security posture and recent security events.
- Adversarial tests for prompt injection, secret leakage, SSRF-like egress, quota exhaustion, redaction canaries, admin-only access, and zero-cost posture.

## Architecture and security decisions

Phase 10 keeps hard security decisions deterministic and server-side:

- Authentication, authorization, tenant scope, quota enforcement, egress policy, citation validation, and research approval do not depend on a model classifier.
- Guardrail scanners add deterministic prevention/detection for known adversarial patterns and are intentionally reproducible in CI.
- Security events store safe metadata only. Raw prompts, raw document bodies, raw provider payloads, and secrets are not persisted in security telemetry.
- Quota exhaustion records an event in a separate successful transaction before returning a throttled error.
- Search authorization now runs before deterministic query embedding or retrieval work.

## Zero-cost path

The Phase 10 gate uses:

- Local PostgreSQL for authoritative metadata, quotas, and security events.
- Deterministic development authentication.
- Deterministic local parser/chunker/embedding/retrieval/generation/evaluation/research/security behavior.
- No paid model API, cloud service, hosted scanner, managed DLP, managed rate-limit service, or external egress.

Optional billable or enterprise security integrations remain disabled by default.

## Validation evidence

Phase-specific evidence:

- Migration `0009_phase9 -> 0010_phase10` applied successfully.
- API focused Phase 10 tests: `3 passed`.
- API lint: passed.
- API typecheck: passed.
- Web lint: passed.
- Web typecheck: passed.
- OpenAPI export: passed.
- Shared TypeScript contract generation: passed.

The full repository lint, typecheck, test, build, and browser demonstration are part of the final Phase 10 product gate.

## Security and failure scenarios covered

- Normal admin posture request succeeds.
- Member/viewer/non-member security event access is denied without disclosing tenant data.
- Prompt-injection and secret-exfiltration-like input is blocked.
- Secret-like values are redacted from error/event evidence.
- Repeated search abuse is throttled with a stable resource-exhausted error.
- Quota exhaustion persists a security event even though the abusive request fails.
- Egress policy blocks non-HTTPS, loopback/private/link-local/reserved, and metadata-service targets.
- Generated output containing secret-like content fails closed.

## Residual risks

- Pattern-based deterministic scanners can miss novel attacks; they are a baseline, not a complete security program.
- Malware scanning, sandboxed rich-file conversion, external penetration testing, compliance certification, enterprise DLP/KMS/HSM, SAML/SCIM, and 24/7 incident operations require production/customer scope.
- `content_trust_records` and `retention_tombstones` are implemented as persistence foundations; full quarantine/deletion workflows remain future hardening work.
- PostgreSQL fixed-window quotas are sufficient for the local product gate; distributed rate limiting should be evaluated for high-scale deployments.
