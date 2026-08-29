terraform {
  required_version = ">= 1.6.0"
}

variable "enable_billable_resources" {
  description = "Must be explicitly true before any future AWS resource module can create billable infrastructure."
  type        = bool
  default     = false

  validation {
    condition     = var.enable_billable_resources == false
    error_message = "Billable AWS resources require a separately reviewed Terraform change and explicit approval."
  }
}

variable "aws_region" {
  description = "Target single-region deployment once provisioning is explicitly approved."
  type        = string
  default     = "us-east-1"
}

locals {
  baseline_version = "phase11-aws-baseline-v1"
  service_boundaries = {
    api = {
      inbound  = ["https_from_load_balancer"]
      outbound = ["postgres", "object_storage", "redis", "model_provider_adapter_if_enabled"]
    }
    worker = {
      inbound  = ["private_service_network"]
      outbound = ["postgres", "object_storage", "redis", "model_provider_adapter_if_enabled"]
    }
    web = {
      inbound  = ["https_from_internet"]
      outbound = ["api_private_endpoint"]
    }
  }
  least_privilege_policies = {
    api = {
      allowed_actions = [
        "secretsmanager:GetSecretValue",
        "kms:Decrypt",
        "s3:GetObject",
        "s3:PutObject",
      ]
      denied_by_default = [
        "iam:*",
        "organizations:*",
        "s3:DeleteBucket",
      ]
    }
    worker = {
      allowed_actions = [
        "secretsmanager:GetSecretValue",
        "kms:Decrypt",
        "s3:GetObject",
        "s3:PutObject",
      ]
      denied_by_default = [
        "iam:*",
        "organizations:*",
        "s3:DeleteBucket",
      ]
    }
    ci = {
      allowed_actions = [
        "sts:AssumeRoleWithWebIdentity",
      ]
      denied_by_default = [
        "iam:CreateAccessKey",
        "iam:UpdateAccessKey",
      ]
    }
  }
}

output "baseline_version" {
  value = local.baseline_version
}

output "billable_resource_creation_enabled" {
  value = var.enable_billable_resources
}

output "service_boundaries" {
  value = local.service_boundaries
}

output "least_privilege_policies" {
  value = local.least_privilege_policies
}
