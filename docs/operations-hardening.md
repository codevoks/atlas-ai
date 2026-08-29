# Operations hardening

Phase 11 establishes Atlas AI's production-readiness baseline while preserving the default
zero-cost build, test, and demo path.

## Local observability

The API records bounded local telemetry through a narrow in-process sink:

- `X-Request-ID` correlates client-visible errors.
- `X-Trace-ID` correlates request handling across local diagnostics.
- Route metrics are recorded by route template, HTTP method, status code, and duration.
- Request bodies, response bodies, prompts, document text, retrieved chunks, model output,
  provider payloads, credentials, and raw tenant content are not recorded.
- Hosted telemetry export is disabled by default.

Telemetry is non-authoritative. A telemetry sink failure must not corrupt product state or block
core request correctness.

## Operational posture APIs

Owners and admins can inspect workspace operations posture at:

```text
GET /v1/workspaces/{workspace_id}/operations/posture
```

The response includes:

- telemetry schema and posture version;
- zero-cost and paid-services-disabled status;
- dependency status;
- SLO objectives and observed local route metrics;
- capacity bottleneck watchlist;
- cost posture;
- incident runbook summaries.

Internal aggregate metrics are available at:

```text
GET /internal/ops/metrics
```

This endpoint requires `X-Atlas-Internal-Token`. Production configuration fails closed if the
internal operations token is missing.

## SLO baseline

The initial SLO values are intentionally conservative local objectives:

| SLI | Default objective |
|---|---:|
| API route p95 latency | 750 ms |
| Search p95 latency | 1,500 ms |
| Answer p95 latency | 3,000 ms |
| Research resume p95 latency | 3,000 ms |

These are baseline guardrails, not customer-facing commitments. Real production SLOs must be set
from representative traffic, corpus size, provider latency, and tenant expectations.

## CI and containers

The GitHub Actions workflow validates migrations, hardening artifacts, lint, typecheck, tests, and
builds against a local PostgreSQL service. It does not request cloud credentials, apply Terraform,
provision domains, or call paid model APIs.

Dockerfiles exist for:

- `apps/api`
- `apps/worker`
- `apps/web`

The images do not include secrets. Runtime configuration must be provided through environment
variables or a deployment secret manager.

## AWS/Terraform baseline

`infra/aws` is plan-only in the default repository path:

- no Terraform `resource` blocks;
- no provider credentials;
- `enable_billable_resources = false`;
- least-privilege service-boundary and IAM-policy intent as outputs.

Any real AWS deployment requires a future approved change that adds provider configuration, remote
state locking, OIDC trust, encrypted storage, network controls, secret rotation, backup/restore
policy, rollout/rollback procedures, and explicit approval before billable provisioning.

## Scale and OpenSearch decision

PostgreSQL remains authoritative. OpenSearch is not adopted in Phase 11 because no measured trigger
has been met. Adoption still requires:

- representative workload evidence showing PostgreSQL search SLO/feature limits;
- asynchronous derived projection design;
- shadow-read comparison;
- reconciliation and lag monitoring;
- cutover flag;
- rollback path.

## Reproducible hardening check

Run:

```text
pnpm run ops:validate
```

Expected output:

```text
phase11_artifact_validation=passed
billable_provisioning=disabled
terraform_resources=0
```
