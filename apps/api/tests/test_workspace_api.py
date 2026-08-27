from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from atlas_api.infrastructure.database import create_engine
from tests.conftest import make_settings


async def create_workspace(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    name: str = "Acme Knowledge",
    key: str = "workspace-create-1",
) -> dict[str, object]:
    response = await client.post(
        "/v1/workspaces",
        headers={**headers, "Idempotency-Key": key},
        json={"name": name},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


@pytest.mark.asyncio
async def test_workspace_creation_is_idempotent_and_audited(
    client: AsyncClient, alice_headers: dict[str, str]
) -> None:
    first = await create_workspace(client, alice_headers)

    replay = await client.post(
        "/v1/workspaces",
        headers={**alice_headers, "Idempotency-Key": "workspace-create-1"},
        json={"name": "Acme Knowledge"},
    )
    assert replay.status_code == 200, replay.text
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert replay.json() == first

    conflict = await client.post(
        "/v1/workspaces",
        headers={**alice_headers, "Idempotency-Key": "workspace-create-1"},
        json={"name": "Different Name"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "conflict"

    engine = create_engine(make_settings())
    try:
        async with engine.connect() as connection:
            audit_count = await connection.scalar(text("SELECT count(*) FROM audit_events"))
        assert audit_count == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cross_tenant_workspace_lookup_is_non_disclosing(
    client: AsyncClient,
    alice_headers: dict[str, str],
    bob_headers: dict[str, str],
) -> None:
    alice_workspace = await create_workspace(client, alice_headers, key="alice-workspace")
    await create_workspace(client, bob_headers, name="Bob Workspace", key="bob-workspace")

    response = await client.get(f"/v1/workspaces/{alice_workspace['id']}", headers=bob_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_member_flow_enforces_roles_and_owner_invariant(
    client: AsyncClient,
    alice_headers: dict[str, str],
    bob_headers: dict[str, str],
) -> None:
    workspace = await create_workspace(client, alice_headers, key="member-flow")
    workspace_id = workspace["id"]

    bob_me = await client.get("/v1/me", headers=bob_headers)
    assert bob_me.status_code == 200, bob_me.text
    bob_id = bob_me.json()["id"]

    add_member = await client.post(
        f"/v1/workspaces/{workspace_id}/members",
        headers=alice_headers,
        json={"email": "bob@example.com", "role": "member"},
    )
    assert add_member.status_code == 201, add_member.text

    forbidden_rename = await client.patch(
        f"/v1/workspaces/{workspace_id}",
        headers=bob_headers,
        json={"name": "Renamed By Member", "version": workspace["version"]},
    )
    assert forbidden_rename.status_code == 403

    alice_me = await client.get("/v1/me", headers=alice_headers)
    owner_id = alice_me.json()["id"]
    remove_last_owner = await client.delete(
        f"/v1/workspaces/{workspace_id}/members/{owner_id}",
        headers=alice_headers,
    )
    assert remove_last_owner.status_code == 409

    downgrade_last_owner = await client.patch(
        f"/v1/workspaces/{workspace_id}/members/{owner_id}",
        headers=alice_headers,
        json={"role": "admin", "version": 1},
    )
    assert downgrade_last_owner.status_code == 409
    assert "owner" in downgrade_last_owner.json()["error"]["message"].lower()

    update_bob = await client.patch(
        f"/v1/workspaces/{workspace_id}/members/{bob_id}",
        headers=alice_headers,
        json={"role": "viewer", "version": 1},
    )
    assert update_bob.status_code == 200, update_bob.text
    assert update_bob.json()["role"] == "viewer"


@pytest.mark.asyncio
async def test_authentication_required(client: AsyncClient) -> None:
    response = await client.get("/v1/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


@pytest.mark.asyncio
async def test_unknown_workspace_id_returns_not_found(
    client: AsyncClient, alice_headers: dict[str, str]
) -> None:
    response = await client.get(f"/v1/workspaces/{uuid.uuid4()}", headers=alice_headers)

    assert response.status_code == 404
