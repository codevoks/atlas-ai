# AWS baseline

This directory documents a least-privilege single-region AWS deployment baseline without
provisioning resources by default.

The Terraform in this directory is intentionally plan-only documentation for Phase 11:

- It contains no `resource` blocks.
- It has no default AWS provider credentials.
- `enable_billable_resources` defaults to `false`.
- It emits least-privilege policy documents and network boundary assumptions that can be used as
  implementation input only after explicit provisioning approval.

Billable AWS resources, domains, hosted observability, managed queues, managed search, or paid model
providers must be added through a future approved deployment change. Do not run `terraform apply`
against production accounts from the default repository path.
