from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    terraform = (ROOT / "infra/aws/main.tf").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    _assert("terraform apply" not in ci, "CI must not apply Terraform")
    _assert("aws-actions/configure-aws-credentials" not in ci, "CI must not request AWS credentials")
    _assert(
        re.search(r'(?m)^resource\s+"', terraform) is None,
        "Phase 11 AWS baseline must not declare resources",
    )
    _assert('default     = false' in terraform, "Billable resource creation must default to false")
    _assert("postgres:17.6-alpine" in compose, "Local zero-cost PostgreSQL must remain available")
    _assert("OPS_INTERNAL_TOKEN" in ci, "CI must exercise protected operations configuration")

    print("phase11_artifact_validation=passed")
    print("billable_provisioning=disabled")
    print("terraform_resources=0")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


if __name__ == "__main__":
    main()
