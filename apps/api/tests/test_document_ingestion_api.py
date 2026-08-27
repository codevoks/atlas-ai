from __future__ import annotations

import hashlib
from typing import Any

import pytest
from httpx import AsyncClient

from atlas_api.domain.models import IngestionJobState
from atlas_api.infrastructure.database import create_engine, create_session_factory
from atlas_api.infrastructure.repositories import SqlAlchemyIngestionJobStore
from tests.support import make_settings


async def create_workspace(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    key: str = "phase2-workspace",
) -> dict[str, Any]:
    response = await client.post(
        "/v1/workspaces",
        headers={**headers, "Idempotency-Key": key},
        json={"name": "Phase 2 Workspace"},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


async def create_source(
    client: AsyncClient, headers: dict[str, str], workspace_id: str
) -> dict[str, Any]:
    response = await client.post(
        f"/v1/workspaces/{workspace_id}/sources",
        headers=headers,
        json={"name": "Manual uploads"},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


async def create_uploaded_intent(
    client: AsyncClient,
    headers: dict[str, str],
    workspace_id: str,
    body: bytes,
    *,
    filename: str = "policy.txt",
    media_type: str = "text/plain",
) -> dict[str, Any]:
    digest = hashlib.sha256(body).hexdigest()
    intent_response = await client.post(
        f"/v1/workspaces/{workspace_id}/uploads",
        headers=headers,
        json={
            "original_filename": filename,
            "media_type": media_type,
            "byte_size": len(body),
            "digest_sha256": digest,
        },
    )
    assert intent_response.status_code == 201, intent_response.text
    intent = dict(intent_response.json())
    assert f"workspaces/{workspace_id}/uploads/" in intent["object_key"]

    upload_response = await client.put(
        intent["upload_url"],
        headers={"Content-Type": media_type},
        content=body,
    )
    assert upload_response.status_code == 200, upload_response.text
    assert upload_response.json()["status"] == "uploaded"
    return intent


@pytest.mark.asyncio
async def test_upload_finalize_is_idempotent_and_tenant_scoped(
    client: AsyncClient,
    alice_headers: dict[str, str],
    bob_headers: dict[str, str],
) -> None:
    workspace = await create_workspace(client, alice_headers)
    workspace_id = str(workspace["id"])
    source = await create_source(client, alice_headers, workspace_id)
    intent = await create_uploaded_intent(client, alice_headers, workspace_id, b"phase 2 document")

    finalize = await client.post(
        f"/v1/workspaces/{workspace_id}/uploads/{intent['id']}/finalize",
        headers={**alice_headers, "Idempotency-Key": "finalize-phase2-1"},
        json={"source_id": source["id"], "title": "Policy"},
    )
    assert finalize.status_code == 201, finalize.text
    payload = finalize.json()
    assert payload["document"]["title"] == "Policy"
    assert payload["document_version"]["status"] == "ingestion_pending"
    assert payload["ingestion_job"]["state"] == "pending"

    replay = await client.post(
        f"/v1/workspaces/{workspace_id}/uploads/{intent['id']}/finalize",
        headers={**alice_headers, "Idempotency-Key": "finalize-phase2-1"},
        json={"source_id": source["id"], "title": "Policy"},
    )
    assert replay.status_code == 200, replay.text
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert replay.json()["document"]["id"] == payload["document"]["id"]

    cross_tenant_list = await client.get(
        f"/v1/workspaces/{workspace_id}/documents", headers=bob_headers
    )
    assert cross_tenant_list.status_code == 404


@pytest.mark.asyncio
async def test_upload_rejects_bad_token_and_digest_mismatch(
    client: AsyncClient, alice_headers: dict[str, str]
) -> None:
    workspace = await create_workspace(client, alice_headers, key="phase2-failure")
    workspace_id = str(workspace["id"])
    body = b"trusted bytes"
    digest = hashlib.sha256(body).hexdigest()
    intent_response = await client.post(
        f"/v1/workspaces/{workspace_id}/uploads",
        headers=alice_headers,
        json={
            "original_filename": "notes.txt",
            "media_type": "text/plain",
            "byte_size": len(body),
            "digest_sha256": digest,
        },
    )
    assert intent_response.status_code == 201, intent_response.text
    intent = intent_response.json()

    bad_token = await client.put(
        str(intent["upload_url"]).replace("token=", "token=bad"),
        headers={"Content-Type": "text/plain"},
        content=body,
    )
    assert bad_token.status_code == 422
    assert bad_token.json()["error"]["code"] == "validation_error"

    digest_mismatch = await client.put(
        intent["upload_url"],
        headers={"Content-Type": "text/plain"},
        content=b"tampered-byte",
    )
    assert digest_mismatch.status_code == 422
    assert digest_mismatch.json()["error"]["code"] == "integrity_violation"


@pytest.mark.asyncio
async def test_viewer_can_read_but_cannot_create_storage_resources(
    client: AsyncClient,
    alice_headers: dict[str, str],
    bob_headers: dict[str, str],
) -> None:
    workspace = await create_workspace(client, alice_headers, key="phase2-viewer")
    workspace_id = str(workspace["id"])
    bob_me = await client.get("/v1/me", headers=bob_headers)
    assert bob_me.status_code == 200
    add_member = await client.post(
        f"/v1/workspaces/{workspace_id}/members",
        headers=alice_headers,
        json={"email": "bob@example.com", "role": "viewer"},
    )
    assert add_member.status_code == 201, add_member.text

    read_sources = await client.get(f"/v1/workspaces/{workspace_id}/sources", headers=bob_headers)
    assert read_sources.status_code == 200

    create_source_response = await client.post(
        f"/v1/workspaces/{workspace_id}/sources",
        headers=bob_headers,
        json={"name": "Viewer source"},
    )
    assert create_source_response.status_code == 403

    create_intent = await client.post(
        f"/v1/workspaces/{workspace_id}/uploads",
        headers=bob_headers,
        json={
            "original_filename": "notes.txt",
            "media_type": "text/plain",
            "byte_size": 5,
            "digest_sha256": hashlib.sha256(b"notes").hexdigest(),
        },
    )
    assert create_intent.status_code == 403


@pytest.mark.asyncio
async def test_ingestion_job_lease_blocks_stale_publication(
    client: AsyncClient, alice_headers: dict[str, str]
) -> None:
    workspace = await create_workspace(client, alice_headers, key="phase2-lease")
    workspace_id = str(workspace["id"])
    source = await create_source(client, alice_headers, workspace_id)
    intent = await create_uploaded_intent(client, alice_headers, workspace_id, b"lease test")
    finalize = await client.post(
        f"/v1/workspaces/{workspace_id}/uploads/{intent['id']}/finalize",
        headers={**alice_headers, "Idempotency-Key": "finalize-lease"},
        json={"source_id": source["id"], "title": "Lease Test"},
    )
    assert finalize.status_code == 201, finalize.text
    job_id = finalize.json()["ingestion_job"]["id"]

    engine = create_engine(make_settings())
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session, session.begin():
            store = SqlAlchemyIngestionJobStore(session)
            claimed = await store.claim_next_job("worker-a", lease_seconds=60)
            assert claimed is not None
            assert str(claimed.id) == job_id

        async with session_factory() as session, session.begin():
            store = SqlAlchemyIngestionJobStore(session)
            verifying = await store.transition_job(
                claimed.id,
                "worker-a",
                claimed.version,
                IngestionJobState.VERIFYING,
                progress=35,
                reason="test_verify",
            )

        async with session_factory() as session, session.begin():
            store = SqlAlchemyIngestionJobStore(session)
            with pytest.raises(Exception, match="lease"):
                await store.publish_document_version(claimed.id, "worker-a", claimed.version)

        async with session_factory() as session, session.begin():
            store = SqlAlchemyIngestionJobStore(session)
            completed = await store.publish_document_version(
                claimed.id, "worker-a", verifying.version
            )
            assert completed.state == IngestionJobState.SUCCEEDED
            assert completed.progress == 100
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_document_delete_hides_document_and_requests_job_cancellation(
    client: AsyncClient, alice_headers: dict[str, str]
) -> None:
    workspace = await create_workspace(client, alice_headers, key="phase2-delete")
    workspace_id = str(workspace["id"])
    source = await create_source(client, alice_headers, workspace_id)
    intent = await create_uploaded_intent(client, alice_headers, workspace_id, b"delete test")
    finalize = await client.post(
        f"/v1/workspaces/{workspace_id}/uploads/{intent['id']}/finalize",
        headers={**alice_headers, "Idempotency-Key": "finalize-delete"},
        json={"source_id": source["id"], "title": "Delete Test"},
    )
    assert finalize.status_code == 201, finalize.text
    document_id = finalize.json()["document"]["id"]
    job_id = finalize.json()["ingestion_job"]["id"]

    deleted = await client.delete(
        f"/v1/workspaces/{workspace_id}/documents/{document_id}", headers=alice_headers
    )
    assert deleted.status_code == 204, deleted.text

    get_deleted = await client.get(
        f"/v1/workspaces/{workspace_id}/documents/{document_id}", headers=alice_headers
    )
    assert get_deleted.status_code == 404

    documents = await client.get(f"/v1/workspaces/{workspace_id}/documents", headers=alice_headers)
    assert documents.status_code == 200
    assert documents.json()["items"] == []

    job = await client.get(
        f"/v1/workspaces/{workspace_id}/ingestion-jobs/{job_id}", headers=alice_headers
    )
    assert job.status_code == 200
    assert job.json()["state"] == "cancel_requested"
