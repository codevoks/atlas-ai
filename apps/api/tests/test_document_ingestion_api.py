from __future__ import annotations

import hashlib
import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from atlas_api.application.embeddings import DeterministicLocalEmbeddingProvider, EmbeddingRequest
from atlas_api.application.ports import ChunkDraftRecord, ChunkEmbeddingDraftRecord
from atlas_api.domain.models import IngestionJobState
from atlas_api.infrastructure.database import create_engine, create_session_factory
from atlas_api.infrastructure.repositories import (
    SqlAlchemyDocumentStore,
    SqlAlchemyIngestionJobStore,
)
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


@pytest.mark.asyncio
async def test_published_chunks_are_listed_with_version_provenance_and_tenant_scope(
    client: AsyncClient,
    alice_headers: dict[str, str],
    bob_headers: dict[str, str],
) -> None:
    workspace = await create_workspace(client, alice_headers, key="phase3-chunks")
    workspace_id = str(workspace["id"])
    source = await create_source(client, alice_headers, workspace_id)
    intent = await create_uploaded_intent(
        client,
        alice_headers,
        workspace_id,
        b"# Policy\n\nAtlas keeps tenant data isolated.",
        filename="policy.md",
        media_type="text/markdown",
    )
    finalize = await client.post(
        f"/v1/workspaces/{workspace_id}/uploads/{intent['id']}/finalize",
        headers={**alice_headers, "Idempotency-Key": "finalize-phase3-chunks"},
        json={"source_id": source["id"], "title": "Policy"},
    )
    assert finalize.status_code == 201, finalize.text
    version_id = finalize.json()["document_version"]["id"]
    document_id = finalize.json()["document"]["id"]
    job_id = finalize.json()["ingestion_job"]["id"]

    engine = create_engine(make_settings())
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session, session.begin():
            store = SqlAlchemyIngestionJobStore(session)
            document_store = SqlAlchemyDocumentStore(session)
            claimed = await store.claim_next_job("worker-a", lease_seconds=60)
            assert claimed is not None
            verifying = await store.transition_job(
                claimed.id,
                "worker-a",
                claimed.version,
                IngestionJobState.VERIFYING,
                progress=35,
                reason="test_verify",
            )
            chunking = await store.transition_job(
                claimed.id,
                "worker-a",
                verifying.version,
                IngestionJobState.CHUNKING,
                progress=70,
                reason="test_chunking",
            )
            provider = DeterministicLocalEmbeddingProvider(make_settings())
            batch = await provider.embed(
                [
                    EmbeddingRequest(
                        item_id=claimed.id,
                        text="Atlas keeps tenant data isolated.",
                    )
                ]
            )
            embedding_set = await document_store.active_embedding_set(
                claimed.workspace_id,
                provider=provider.provider,
                model=provider.model,
                model_version=provider.model_version,
                dimension=provider.dimension,
                normalized=provider.normalized,
                config={"zero_cost": True, "storage": "postgres_jsonb_exact_cosine"},
            )
            completed = await store.publish_document_version(
                claimed.id,
                "worker-a",
                chunking.version,
                chunks=[
                    ChunkDraftRecord(
                        ordinal=0,
                        block_type="section",
                        heading="Policy",
                        page_number=None,
                        start_char=0,
                        end_char=42,
                        token_count=6,
                        content_hash=hashlib.sha256(
                            b"Atlas keeps tenant data isolated."
                        ).hexdigest(),
                        text="Atlas keeps tenant data isolated.",
                        safe_metadata={"source_blocks": 2},
                    )
                ],
                embedding_set=embedding_set,
                embeddings=[
                    ChunkEmbeddingDraftRecord(
                        chunk_ordinal=0,
                        vector=batch.items[0].vector,
                        token_count=batch.items[0].token_count,
                    )
                ],
                parser_name="atlas-text-parser",
                parser_version="test",
                chunker_name="atlas-paragraph-chunker",
                chunker_version="test",
                normalized_object_key=f"workspaces/{workspace_id}/derived/{version_id}/normalized.json",
                normalized_digest_sha256=hashlib.sha256(b"normalized").hexdigest(),
                character_count=42,
                token_count=6,
                safe_metadata={"media_type": "text/markdown"},
            )
            assert str(completed.id) == job_id
            assert completed.state == IngestionJobState.SUCCEEDED
    finally:
        await engine.dispose()

    versions = await client.get(
        f"/v1/workspaces/{workspace_id}/documents/{document_id}/versions",
        headers=alice_headers,
    )
    assert versions.status_code == 200, versions.text
    version = versions.json()["items"][0]
    assert version["parser_name"] == "atlas-text-parser"
    assert version["chunk_count"] == 1
    assert version["embedding_count"] == 1
    assert version["embedding_set_id"]
    assert version["token_count"] == 6

    chunks = await client.get(
        f"/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/chunks",
        headers=alice_headers,
    )
    assert chunks.status_code == 200, chunks.text
    assert chunks.json()["items"][0]["text"] == "Atlas keeps tenant data isolated."
    assert chunks.json()["items"][0]["heading"] == "Policy"

    cross_tenant = await client.get(
        f"/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/chunks",
        headers=bob_headers,
    )
    assert cross_tenant.status_code == 404


@pytest.mark.asyncio
async def test_semantic_search_returns_authorized_evidence(
    client: AsyncClient,
    alice_headers: dict[str, str],
    bob_headers: dict[str, str],
) -> None:
    workspace = await create_workspace(client, alice_headers, key="phase4-search")
    workspace_id = str(workspace["id"])
    source = await create_source(client, alice_headers, workspace_id)
    intent = await create_uploaded_intent(
        client,
        alice_headers,
        workspace_id,
        (
            b"# Reliability\n\nRetries recover failed worker crashes.\n\n"
            b"# Billing\n\nInvoices are exported monthly."
        ),
        filename="runbook.md",
        media_type="text/markdown",
    )
    finalize = await client.post(
        f"/v1/workspaces/{workspace_id}/uploads/{intent['id']}/finalize",
        headers={**alice_headers, "Idempotency-Key": "finalize-phase4-search"},
        json={"source_id": source["id"], "title": "Operations Runbook"},
    )
    assert finalize.status_code == 201, finalize.text
    version_id = finalize.json()["document_version"]["id"]

    engine = create_engine(make_settings())
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session, session.begin():
            store = SqlAlchemyIngestionJobStore(session)
            document_store = SqlAlchemyDocumentStore(session)
            claimed = await store.claim_next_job("worker-a", lease_seconds=60)
            assert claimed is not None
            verifying = await store.transition_job(
                claimed.id,
                "worker-a",
                claimed.version,
                IngestionJobState.VERIFYING,
                progress=35,
                reason="test_verify",
            )
            chunking = await store.transition_job(
                claimed.id,
                "worker-a",
                verifying.version,
                IngestionJobState.CHUNKING,
                progress=70,
                reason="test_chunking",
            )
            provider = DeterministicLocalEmbeddingProvider(make_settings())
            batch = await provider.embed(
                [
                    EmbeddingRequest(
                        item_id=claimed.id, text="Retries recover failed worker crashes."
                    ),
                    EmbeddingRequest(
                        item_id=uuid.UUID(source["id"]), text="Invoices are exported monthly."
                    ),
                ]
            )
            embedding_set = await document_store.active_embedding_set(
                claimed.workspace_id,
                provider=provider.provider,
                model=provider.model,
                model_version=provider.model_version,
                dimension=provider.dimension,
                normalized=provider.normalized,
                config={"zero_cost": True, "storage": "postgres_jsonb_exact_cosine"},
            )
            completed = await store.publish_document_version(
                claimed.id,
                "worker-a",
                chunking.version,
                chunks=[
                    ChunkDraftRecord(
                        ordinal=0,
                        block_type="section",
                        heading="Reliability",
                        page_number=None,
                        start_char=0,
                        end_char=39,
                        token_count=5,
                        content_hash=hashlib.sha256(
                            b"Retries recover failed worker crashes."
                        ).hexdigest(),
                        text="Retries recover failed worker crashes.",
                        safe_metadata={"source_blocks": 2},
                    ),
                    ChunkDraftRecord(
                        ordinal=1,
                        block_type="section",
                        heading="Billing",
                        page_number=None,
                        start_char=40,
                        end_char=70,
                        token_count=4,
                        content_hash=hashlib.sha256(b"Invoices are exported monthly.").hexdigest(),
                        text="Invoices are exported monthly.",
                        safe_metadata={"source_blocks": 4},
                    ),
                ],
                embedding_set=embedding_set,
                embeddings=[
                    ChunkEmbeddingDraftRecord(
                        chunk_ordinal=0,
                        vector=batch.items[0].vector,
                        token_count=batch.items[0].token_count,
                    ),
                    ChunkEmbeddingDraftRecord(
                        chunk_ordinal=1,
                        vector=batch.items[1].vector,
                        token_count=batch.items[1].token_count,
                    ),
                ],
                parser_name="atlas-text-parser",
                parser_version="test",
                chunker_name="atlas-paragraph-chunker",
                chunker_version="test",
                normalized_object_key=f"workspaces/{workspace_id}/derived/{version_id}/normalized.json",
                normalized_digest_sha256=hashlib.sha256(b"normalized").hexdigest(),
                character_count=70,
                token_count=9,
                safe_metadata={"media_type": "text/markdown"},
            )
            assert completed.state == IngestionJobState.SUCCEEDED
    finally:
        await engine.dispose()

    search = await client.post(
        f"/v1/workspaces/{workspace_id}/search/semantic",
        headers=alice_headers,
        json={"query": "worker retry crash recovery", "top_k": 3, "debug": True},
    )
    assert search.status_code == 200, search.text
    payload = search.json()
    assert payload["debug"]["paid_services"] is False
    assert payload["items"]
    assert payload["items"][0]["document_title"] == "Operations Runbook"
    assert "Retries recover failed worker crashes" in payload["items"][0]["snippet"]
    assert payload["items"][0]["embedding_set_id"]

    lexical = await client.post(
        f"/v1/workspaces/{workspace_id}/search",
        headers=alice_headers,
        json={"query": "Invoices monthly", "mode": "lexical", "top_k": 3, "debug": True},
    )
    assert lexical.status_code == 200, lexical.text
    lexical_payload = lexical.json()
    assert lexical_payload["mode"] == "lexical"
    assert lexical_payload["retrieval_config_version"] == "phase5-postgres-fts-rrf-v1"
    assert lexical_payload["debug"]["paid_services"] is False
    assert lexical_payload["debug"]["query_persisted"] is False
    assert lexical_payload["items"][0]["retrieval_stage"] == "lexical"
    assert "Invoices are exported monthly" in lexical_payload["items"][0]["snippet"]

    hybrid = await client.post(
        f"/v1/workspaces/{workspace_id}/search",
        headers=alice_headers,
        json={"query": "Invoices monthly", "mode": "hybrid", "top_k": 5, "debug": True},
    )
    assert hybrid.status_code == 200, hybrid.text
    hybrid_payload = hybrid.json()
    assert hybrid_payload["mode"] == "hybrid"
    assert hybrid_payload["debug"]["branch_counts"]["semantic"] >= 1
    assert hybrid_payload["debug"]["branch_counts"]["lexical"] >= 1
    assert hybrid_payload["debug"]["branch_counts"]["final"] == len(hybrid_payload["items"])
    assert {item["retrieval_stage"] for item in hybrid_payload["items"]} == {"hybrid"}
    assert any(item["rrf_score"] is not None for item in hybrid_payload["items"])

    special_chars = await client.post(
        f"/v1/workspaces/{workspace_id}/search",
        headers=alice_headers,
        json={"query": "worker + retry: crash? <script>", "mode": "lexical", "top_k": 3},
    )
    assert special_chars.status_code == 200, special_chars.text

    backfill = await client.post(
        f"/v1/workspaces/{workspace_id}/embeddings/backfill",
        headers=alice_headers,
        json={"limit": 10},
    )
    assert backfill.status_code == 200, backfill.text
    assert backfill.json()["embedded_count"] == 0
    assert backfill.json()["missing_after"] == 0

    cross_tenant_search = await client.post(
        f"/v1/workspaces/{workspace_id}/search/semantic",
        headers=bob_headers,
        json={"query": "worker retry crash recovery", "top_k": 3},
    )
    assert cross_tenant_search.status_code == 404

    cross_tenant_hybrid = await client.post(
        f"/v1/workspaces/{workspace_id}/search",
        headers=bob_headers,
        json={"query": "worker retry crash recovery", "mode": "hybrid", "top_k": 3},
    )
    assert cross_tenant_hybrid.status_code == 404


@pytest.mark.asyncio
async def test_semantic_search_rejects_invalid_bounds(
    client: AsyncClient,
    alice_headers: dict[str, str],
) -> None:
    workspace = await create_workspace(client, alice_headers, key="phase4-bounds")
    workspace_id = str(workspace["id"])
    empty_query = await client.post(
        f"/v1/workspaces/{workspace_id}/search/semantic",
        headers=alice_headers,
        json={"query": "   ", "top_k": 3},
    )
    assert empty_query.status_code == 422

    too_many = await client.post(
        f"/v1/workspaces/{workspace_id}/search",
        headers=alice_headers,
        json={"query": "tenant isolation", "mode": "hybrid", "top_k": 21},
    )
    assert too_many.status_code == 422
