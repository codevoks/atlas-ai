# Phase 11 — Scale evidence, observability, AWS/Terraform, and production hardening

## Scope

Instrument OpenTelemetry and Langfuse; define SLOs from measured product needs; load/soak/failure test; profile and optimize cost/latency; benchmark pgvector/PostgreSQL lexical against OpenSearch only if trigger criteria are met; containerize; provision a least-privilege single-region AWS baseline with Terraform; create GitHub Actions CI/CD; validate backup/restore, migrations, rollout/rollback, scaling, and operational runbooks.

## Engineering concepts

SLIs/SLOs/error budgets, RED/USE signals, traces/metrics/logs, AI trace privacy, capacity/load/soak testing, queueing/backpressure, connection pools, autoscaling, cost attribution, IaC state, IAM/networking, deployment strategies, disaster recovery, search-engine tradeoffs and operational burden.

## Architecture changes and modules

Add instrumentation SDK boundary, trace propagation through HTTP/jobs/research, Langfuse adapter with content-off defaults, metrics/dashboards/alerts, containers, Terraform modules, CI/CD pipelines, environment promotion, migration/reindex controllers, backup/restore and runbooks. Split worker pools by workload if tests show contention.

If an OpenSearch trigger is met—PostgreSQL search SLO/recall fails at representative scale, required analyzer/facet/search features are unavailable, or isolation/operational needs justify it—build an asynchronous derived projection, dual-read shadow comparison, reconciliation, cutover flag, and rollback. PostgreSQL remains authoritative.

## Data model changes

Add operational configuration/version references, search projection cursors/tombstones if OpenSearch is used, usage/cost aggregates that avoid raw content, deployment/schema compatibility metadata, and retention indexes/partitions where measured. No telemetry warehouse in the transactional schema without evidence.

## APIs

Truthful liveness/readiness (readiness checks critical dependencies without cascading overload), operational metrics on protected internal endpoints, admin reindex/reconciliation/status commands, and safe usage views. Public contracts remain backward compatible; deployment supports expand/migrate/contract schema changes.

## Important interfaces

`Tracer/Meter`; `AITraceSink`; `CostAttributor`; `HealthCheck`; `LoadScenario`; `SearchProjectionWriter/Reader`; `ProjectionReconciler`; `FeatureFlag`; `BackupVerifier`; `DeploymentMetadata`. Telemetry failure never breaks core correctness and buffers/drops within bounds.

## Security requirements

Private networking/security groups, TLS, encryption at rest, least-privilege IAM per service, managed secret store and rotation, no long-lived CI cloud keys (OIDC), protected environments, pinned/scanned builds, non-public databases/buckets/Redis/search, WAF/rate limits as justified, encrypted Terraform state with locking, redacted access-controlled telemetry, backup access/restore audit.

## Failure scenarios

Traffic spike/noisy tenant; DB pool exhaustion; queue backlog/provider throttle; autoscaling lag; telemetry exporter outage/backpressure; bad migration/deploy; partial region/service outage; corrupt backup; OpenSearch lag/split-brain projection; reindex during writes; cache stampede; cost anomaly; Terraform drift/state lock. Runbooks define detection, containment, rollback, recovery, and communication.

## Testing strategy

Representative load model with declared assumptions; load/soak/spike and tenant-fairness tests; chaos/fault injection for dependencies; trace completeness/redaction and alert tests; migration compatibility/rollback rehearsal; backup restore and derived-index rebuild drill; Terraform validate/plan/policy checks; image/dependency scan; CI branch/protected deployment checks; pgvector/OpenSearch shadow evaluation if triggered.

## Acceptance criteria

Measured capacity envelope and bottlenecks are documented; SLOs/alerts map to user outcomes; cost per successful ingestion/search/answer/research is attributable; restore and rollback drills succeed; infrastructure is reproducible and least privilege; telemetry leaks no canary content; OpenSearch is either adopted with benchmark/cutover evidence or explicitly rejected/deferred with results.

## Engineering review focus and implementation drills

Useful implementation drills: estimate QPS/storage/queue/model load; add a cross-service trace; diagnose a latency trace; design load scenarios; fix a zero-downtime migration; compare pgvector/OpenSearch benchmark data; write an incident runbook; review IAM/Terraform for excess privilege.

## System-design review focus

Explain first 100× bottlenecks, 10M-document options, partition/shard/tenant placement, backpressure and fairness, replicas/consistency, SLO/error budgets, cost optimization without quality loss, OpenSearch tradeoffs, IaC state/IAM, deployment migration safety, RTO/RPO and restore evidence.

## Explicit deferrals and final boundary

Multi-region active-active, Kubernetes, microservice decomposition, enterprise compliance certification, every provider integration, every connector, and multi-agent behavior require explicit product/scale evidence. Final completion proves a defensible production baseline, not infinite feature coverage. After the final product gate, stop and report remaining risks/backlog.
