from __future__ import annotations

import pytest
from httpx import AsyncClient
from pydantic import ValidationError as PydanticValidationError

from atlas_api.config import Settings
from tests.test_workspace_api import create_workspace


@pytest.mark.asyncio
async def test_operations_posture_is_admin_only_and_tenant_safe(
    client: AsyncClient,
    alice_headers: dict[str, str],
    bob_headers: dict[str, str],
) -> None:
    workspace = await create_workspace(client, alice_headers, key="phase11-ops-posture")
    workspace_id = workspace["id"]

    health = await client.get("/health/live", headers=alice_headers)
    assert health.status_code == 200
    assert "x-trace-id" in health.headers

    posture = await client.get(
        f"/v1/workspaces/{workspace_id}/operations/posture", headers=alice_headers
    )
    assert posture.status_code == 200, posture.text
    payload = posture.json()
    assert payload["posture_version"] == "phase11-production-hardening-v1"
    assert payload["telemetry_schema_version"] == "phase11-local-telemetry-v1"
    assert payload["zero_cost"] is True
    assert payload["paid_services_enabled"] is False
    assert payload["telemetry_exporter"] == "local"
    assert payload["telemetry_content_capture_enabled"] is False
    assert payload["dependency_status"]["database"] == "ready"
    assert payload["cost_summary"]["demo_cost_usd"] == 0.0
    assert payload["cost_summary"]["paid_cloud_required"] is False
    assert payload["capacity_envelope"]["search_projection"] == (
        "postgresql_authoritative_no_opensearch_trigger"
    )
    assert len(payload["runbooks"]) >= 3
    assert any(route["route"] == "/health/live" for route in payload["routes"])
    assert "alice@example.com" not in str(payload)
    assert "sk-proj" not in str(payload)

    bob_posture = await client.get(
        f"/v1/workspaces/{workspace_id}/operations/posture", headers=bob_headers
    )
    assert bob_posture.status_code == 404, bob_posture.text


@pytest.mark.asyncio
async def test_internal_metrics_endpoint_requires_explicit_token(
    client: AsyncClient,
) -> None:
    missing = await client.get("/internal/ops/metrics")
    assert missing.status_code == 403, missing.text

    wrong = await client.get(
        "/internal/ops/metrics",
        headers={"X-Atlas-Internal-Token": "wrong-token"},
    )
    assert wrong.status_code == 403, wrong.text

    allowed = await client.get(
        "/internal/ops/metrics",
        headers={"X-Atlas-Internal-Token": "atlas-phase11-test-ops-internal-token"},
    )
    assert allowed.status_code == 200, allowed.text
    payload = allowed.json()
    assert payload["dependency_status"]["database"] == "not_checked"
    assert payload["telemetry_content_capture_enabled"] is False


def test_production_requires_internal_operations_token() -> None:
    with pytest.raises(PydanticValidationError):
        Settings(
            atlas_env="production",
            auth_mode="oidc",
            auth_jwks_url="https://issuer.example/.well-known/jwks.json",
            upload_signing_secret="atlas-phase2-test-upload-signing-secret",  # noqa: S106
        )
