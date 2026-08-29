# Phase 10 — AI security, guardrails, and adversarial assurance

## Scope

Consolidate the security controls built in Phases 1–9; implement missing deterministic/model-assisted guardrails; adversarially test authentication, tenant isolation, uploads, retrieval poisoning, indirect prompt injection, citation manipulation, tools, outputs, budgets, rate abuse, secrets, logs, and dependency/configuration posture. Produce a residual-risk and incident-response readiness report. The default security suite must run with deterministic local fixtures/fakes and zero monetary cost.

## Engineering concepts

Threat modeling, defense in depth, policy enforcement, deterministic versus model-assisted guardrails, confused deputy, prompt/indirect injection, retrieval poisoning, exfiltration, SSRF, IDOR, output encoding, sensitive-data handling, denial-of-wallet, red teaming, security test limitations and safe failure.

## Architecture changes and modules

Add or harden centralized policy enforcement, content trust labels, input/output scanners/validators, egress/tool policy, quota/rate/budget controls, security event sink, redaction, retention/deletion workflows, adversarial test harness, and operational runbooks. Model classifiers can add signals but cannot decide authentication/authorization alone.

## Data model changes

Add versioned policy configuration, security-event references, quota/budget counters/reservations, content trust/quarantine status, approval/policy outcomes, retention/deletion tombstones where absent. Store minimal safe metadata; do not build a new sensitive-content lake.

## APIs

No arbitrary “guardrail bypass.” Admin policy/config endpoints require strong authorization, validation, versioning, audit, and safe defaults. Quota responses use stable non-sensitive error codes. Deletion/export and incident operations have explicit asynchronous status and idempotency where scoped.

## Important interfaces

`PolicyEngine`; `InputValidator`; `OutputValidator`; `ContentTrustClassifier`; `EgressPolicy`; `RateLimiter`; `BudgetLedger`; `Redactor`; `SecurityEventSink`; `RetentionService`; `AdversarialCaseRunner`. Define fail-open/closed behavior for every control and test it.

## Security requirements

Meet every control and test in `docs/threat-model.md`; least privilege IAM/DB/object/tool identities; tenant-filter parity; prompt/data separation; citation/source validation; sanitized rendering; egress restrictions; provider privacy; secret rotation readiness; dependency/SBOM/container scanning; abuse limits; audit access/retention; incident containment. Document controls not possible locally and their production verification, but do not require paid APIs/cloud for the product gate.

## Failure scenarios

Guardrail/model unavailable; false positive/negative; rate store unavailable; policy rollout misconfiguration; attacker splits payload across chunks; poisoned high-rank source; secret appears in model/tool output; log redactor fails; deletion races index/cache/checkpoint; revoked user resumes research; dependency CVE; abuse distributed across accounts. Security-critical ambiguity fails closed with a usable recovery path.

## Testing strategy

Threat-to-test traceability; authorization mutation/fuzz/property tests; adversarial upload/parser corpus kept small; prompt injection/poisoning/citation suites; SSRF/redirect/tool smuggling; budget/rate concurrency; XSS/output tests; redaction canaries; dependency/IaC/container scans where available; manual architecture red team; regression suite deterministic and CI-safe.

## Acceptance criteria

All critical threat paths have prevention/detection and executable evidence; no known cross-tenant leak or unbounded agent/model/tool path; content/tool authority is explicit; logs/traces pass canary scans; incident and key-rotation/deletion workflows are documented/tested proportionally; residual risks have owner, severity, mitigation, and acceptance—not silence.

## Engineering review focus and implementation drills

Useful implementation drills: threat model a new connector; exploit/fix an IDOR; malicious retrieved-document test; citation tampering test; SSRF-safe URL policy; concurrency-safe token budget; critique a prompt-only guardrail and design layered controls.

## System-design review focus

Explain why guardrails are not one library, trust/authority flow, deterministic versus probabilistic controls, indirect injection, retrieval poisoning, tool least privilege, denial-of-wallet, safe logging, security/UX tradeoffs, residual risk, and incident containment.

## Explicit deferrals

External penetration test, compliance certification, enterprise DLP/KMS/HSM/residency, SAML/SCIM, and 24/7 incident operations require organizational/customer scope. They must be production backlog entries, never claimed as complete.
