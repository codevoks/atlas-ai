# Phase 1 — Foundation, authentication, tenancy, and RBAC

## Scope

Create the pnpm/Turborepo skeleton; Next.js web with Tailwind CSS, FastAPI API, and worker health seam; shared config/contract generation; local PostgreSQL only as needed; migrations; authentication integration; workspace lifecycle; membership/RBAC; audit events; CI-quality commands. Deliver a thin authenticated vertical slice, not document ingestion.

## Engineering concepts

Monorepo task graphs, browser/BFF/API boundaries, OIDC/session/token validation, dependency injection, transactions, RBAC versus ABAC, tenant isolation, IDOR, migration safety, OpenAPI contract generation, structured errors, auditability, test pyramids.

## Architecture changes and modules

Instantiate `apps/web`, `apps/api`, `apps/worker`, `packages/config`, `packages/shared-types`. API modules: domain identities/workspaces/memberships/permissions; application use cases; repository/unit-of-work ports; SQL infrastructure; auth middleware/dependencies; REST routes. Web modules: session boundary, typed API client, Tailwind CSS styling, workspace selector/member UI. Worker has only configuration, service identity, health, and testable startup.

## Data model changes

Add `users`, `workspaces`, `memberships`, `audit_events`, schema migration metadata, and optional invitations if explicitly scoped. Enforce unique identity subject, unique active membership, role enum/check, workspace-aware keys, timestamps, and at least one-owner invariant in transactional use cases. Do not store provider access tokens in ordinary plaintext columns.

## APIs

`GET /v1/me`; create/list/get/update workspace; list/add/update/remove members or invitations; health/readiness endpoints. Workspace context is derived from authenticated membership. Define stable error envelope, cursor pagination, request IDs, idempotency for workspace/invite creation, and OpenAPI-to-TypeScript contract checks.

## Important interfaces

`IdentityVerifier.verify`; `CurrentActorResolver.resolve`; `AuthorizationPolicy.require`; `WorkspaceRepository`; `MembershipRepository`; `AuditSink`; `UnitOfWork`; clock/ID ports for deterministic tests. Permission checks live in use cases and typed repositories always require workspace scope.

## Security requirements

Secure cookies/token audience/issuer/expiry, CSRF decision, CORS allowlist, CSP/safe rendering, no open redirect, generic auth errors, least-privilege DB identities, anti-IDOR tests, role/ownership escalation prevention, revoked membership behavior, rate limits on auth/admin operations, redacted logs and secrets via environment/secret-store boundary.

## Failure scenarios

Identity provider unavailable or JWKS rotated; stale/revoked session; duplicate create retry; concurrent last-owner removal; DB deadlock; migration failure; web/API contract drift; audit write failure. Decide whether audit is transactionally required per mutation; fail closed for authorization ambiguity.

## Testing strategy

Domain permission matrices; use-case unit tests; repository integration tests against PostgreSQL; migration up/down or forward-fix validation; API contract/error tests; cross-tenant resource substitution; browser smoke flow; lint/typecheck/build; configuration and secret-scanning tests. No live identity dependency in deterministic CI.

## Acceptance criteria

An authenticated user can operate only in active workspaces permitted by role; cross-tenant IDs return non-disclosing denial; owner invariants survive concurrency; contracts are not duplicated manually; audit records safe actor/action/outcome; all services start and report truthful readiness; phase gate validations pass.

## Engineering review focus and implementation drills

Review authentication versus authorization and tenant isolation from first principles. Useful implementation drills: implement a FastAPI current-actor dependency; write an RBAC policy table and evaluator; fix an IDOR repository; test concurrent last-owner removal; refactor a giant route into use case/ports; sketch token/JWKS failure handling.

## System-design review focus

Defend BFF/API boundaries, application checks plus optional RLS, workspace-in-row duplication, audit atomicity, session revocation tradeoffs, and how identity/authorization scale. Explain failure and cost impacts of an external identity provider.

## Explicit deferrals

No uploads, object store, queues, parsing, retrieval, AI, document ACL hierarchy, SSO/SAML/SCIM, billing, or production cloud. Fine-grained ACLs and RLS require requirements/evidence. Do not add generalized event buses.
