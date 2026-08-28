from __future__ import annotations

import hashlib
import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from atlas_api.application.embeddings import DeterministicLocalEmbeddingProvider, EmbeddingRequest
from atlas_api.application.ports import ChunkDraftRecord, ChunkEmbeddingDraftRecord
from atlas_api.application.retrieval_metrics import (
    citation_quote_coverage,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    substring_coverage,
)
from atlas_api.domain.models import IngestionJobState
from atlas_api.infrastructure.database import create_engine, create_session_factory
from atlas_api.infrastructure.repositories import (
    SqlAlchemyDocumentStore,
    SqlAlchemyIngestionJobStore,
)
from tests.support import make_settings
from tests.test_document_ingestion_api import (
    create_source,
    create_uploaded_intent,
    create_workspace,
)


async def ready_workspace_with_chunk(
    client: AsyncClient, headers: dict[str, str]
) -> tuple[str, str]:
    workspace = await create_workspace(client, headers, key="phase7-workspace")
    workspace_id = str(workspace["id"])
    source = await create_source(client, headers, workspace_id)
    text = "Invoices are exported monthly for finance review."
    body = f"# Finance\n\n{text}".encode()
    intent = await create_uploaded_intent(
        client,
        headers,
        workspace_id,
        body,
        filename="phase7-finance.md",
        media_type="text/markdown",
    )
    finalize = await client.post(
        f"/v1/workspaces/{workspace_id}/uploads/{intent['id']}/finalize",
        headers={**headers, "Idempotency-Key": "phase7-finalize"},
        json={"source_id": source["id"], "title": "Finance Evaluation Fixture"},
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
            batch = await provider.embed([EmbeddingRequest(item_id=claimed.id, text=text)])
            embedding_set = await document_store.active_embedding_set(
                claimed.workspace_id,
                provider=provider.provider,
                model=provider.model,
                model_version=provider.model_version,
                dimension=provider.dimension,
                normalized=provider.normalized,
                config={"zero_cost": True, "storage": "postgres_jsonb_exact_cosine"},
            )
            await store.publish_document_version(
                claimed.id,
                "worker-a",
                chunking.version,
                chunks=[
                    ChunkDraftRecord(
                        ordinal=0,
                        block_type="section",
                        heading="Finance",
                        page_number=None,
                        start_char=0,
                        end_char=len(text),
                        token_count=7,
                        content_hash=hashlib.sha256(text.encode()).hexdigest(),
                        text=text,
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
                character_count=len(text),
                token_count=7,
                safe_metadata={"media_type": "text/markdown"},
            )
    finally:
        await engine.dispose()

    chunks = await client.get(
        f"/v1/workspaces/{workspace_id}/documents/{finalize.json()['document']['id']}"
        f"/versions/{version_id}/chunks",
        headers=headers,
    )
    assert chunks.status_code == 200, chunks.text
    return workspace_id, str(chunks.json()["items"][0]["id"])


def test_metric_oracles() -> None:
    relevant = {
        uuid.UUID("00000000-0000-0000-0000-000000000001"),
        uuid.UUID("00000000-0000-0000-0000-000000000002"),
    }
    ids = [*relevant]
    ranked = [ids[0], uuid.uuid4(), ids[1]]

    assert recall_at_k(relevant_chunk_ids=relevant, ranked_ids=ranked, k=3) == 1.0
    assert precision_at_k(relevant_chunk_ids=relevant, ranked_ids=ranked, k=2) == 0.5
    assert reciprocal_rank(relevant_chunk_ids=relevant, ranked_ids=ranked, k=3) == 1.0
    assert round(ndcg_at_k(relevant_chunk_ids=relevant, ranked_ids=ranked, k=3), 3) == 0.920
    assert substring_coverage(expected_substrings=["Finance Review"], text="finance review") == 1
    assert (
        citation_quote_coverage(
            expected_quotes=["Invoices are exported"],
            actual_quotes=["Invoices are exported monthly."],
        )
        == 1
    )


@pytest.mark.asyncio
async def test_evaluation_dataset_run_and_baseline_flow(
    client: AsyncClient,
    alice_headers: dict[str, str],
    bob_headers: dict[str, str],
) -> None:
    workspace_id, chunk_id = await ready_workspace_with_chunk(client, alice_headers)
    dataset = await client.post(
        f"/v1/workspaces/{workspace_id}/evaluation-datasets",
        headers=alice_headers,
        json={"name": "Phase 7 Golden Set", "description": "Deterministic local fixture"},
    )
    assert dataset.status_code == 201, dataset.text
    version = await client.post(
        f"/v1/workspaces/{workspace_id}/evaluation-datasets/{dataset.json()['id']}/versions",
        headers=alice_headers,
        json={
            "description": "v1",
            "cases": [
                {
                    "query": "How are invoices handled for finance review?",
                    "retrieval_mode": "hybrid",
                    "top_k": 5,
                    "relevant_chunk_ids": [chunk_id],
                    "expected_answer_substrings": ["finance review"],
                    "expected_citation_quotes": ["Invoices are exported monthly"],
                    "slices": ["finance", "hybrid"],
                }
            ],
        },
    )
    assert version.status_code == 201, version.text
    assert version.json()["case_count"] == 1

    run = await client.post(
        f"/v1/workspaces/{workspace_id}/evaluation-runs",
        headers=alice_headers,
        json={"dataset_version_id": version.json()["id"], "run_name": "Phase 7 regression"},
    )
    assert run.status_code == 201, run.text
    payload: dict[str, Any] = run.json()
    assert payload["status"] == "succeeded"
    assert payload["evaluation_config"]["paid_services"] is False
    assert payload["total_cost_usd"] == 0
    assert payload["aggregate_metrics"]["retrieval"]["recall_at_k"] == 1
    assert payload["aggregate_metrics"]["answer"]["citation_verified_rate"] == 1
    assert payload["results"][0]["answer_run_id"]
    assert payload["results"][0]["retrieved_chunk_ids"][0] == chunk_id

    listed = await client.get(
        f"/v1/workspaces/{workspace_id}/evaluation-runs", headers=alice_headers
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"][0]["id"] == payload["id"]

    baseline = await client.post(
        f"/v1/workspaces/{workspace_id}/evaluation-runs/{payload['id']}/baseline",
        headers=alice_headers,
        json={"notes": "Approved deterministic Phase 7 baseline."},
    )
    assert baseline.status_code == 201, baseline.text

    cross_tenant = await client.get(
        f"/v1/workspaces/{workspace_id}/evaluation-runs/{payload['id']}", headers=bob_headers
    )
    assert cross_tenant.status_code == 404


@pytest.mark.asyncio
async def test_evaluation_rejects_unavailable_chunk_labels(
    client: AsyncClient, alice_headers: dict[str, str]
) -> None:
    workspace_id, _chunk_id = await ready_workspace_with_chunk(client, alice_headers)
    dataset = await client.post(
        f"/v1/workspaces/{workspace_id}/evaluation-datasets",
        headers=alice_headers,
        json={"name": "Invalid Labels"},
    )
    assert dataset.status_code == 201, dataset.text
    missing_chunk = "00000000-0000-0000-0000-000000000001"
    version = await client.post(
        f"/v1/workspaces/{workspace_id}/evaluation-datasets/{dataset.json()['id']}/versions",
        headers=alice_headers,
        json={
            "cases": [
                {
                    "query": "missing label",
                    "retrieval_mode": "hybrid",
                    "top_k": 5,
                    "relevant_chunk_ids": [missing_chunk],
                }
            ],
        },
    )
    assert version.status_code == 422
    assert version.json()["error"]["code"] == "validation_error"
