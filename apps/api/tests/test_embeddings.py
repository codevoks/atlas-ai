from __future__ import annotations

import math
import uuid

import pytest

from atlas_api.application.embeddings import (
    DeterministicLocalEmbeddingProvider,
    EmbeddingBatchPlanner,
    EmbeddingRequest,
    cosine_similarity,
)
from atlas_api.domain.errors import ValidationError
from tests.support import make_settings


@pytest.mark.asyncio
async def test_deterministic_embedding_provider_contract() -> None:
    provider = DeterministicLocalEmbeddingProvider(make_settings())
    request = EmbeddingRequest(item_id=uuid.uuid4(), text="tenant isolation tenant")

    first = await provider.embed([request])
    second = await provider.embed([request])

    assert first.provider == "deterministic-local"
    assert first.model == "atlas-local-hash-embedding"
    assert first.dimension == make_settings().embedding_dimension
    assert first.normalized is True
    assert first.items[0].vector == second.items[0].vector
    assert len(first.items[0].vector) == first.dimension
    magnitude = math.sqrt(sum(value * value for value in first.items[0].vector))
    assert magnitude == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_embedding_similarity_prefers_token_overlap() -> None:
    provider = DeterministicLocalEmbeddingProvider(make_settings())
    batch = await provider.embed(
        [
            EmbeddingRequest(item_id=uuid.uuid4(), text="worker retry recovery"),
            EmbeddingRequest(item_id=uuid.uuid4(), text="worker retry crash recovery"),
            EmbeddingRequest(item_id=uuid.uuid4(), text="monthly invoice export"),
        ]
    )

    query, close, distant = [item.vector for item in batch.items]
    assert cosine_similarity(query, close) > cosine_similarity(query, distant)


def test_embedding_batch_planner_enforces_limits() -> None:
    planner = EmbeddingBatchPlanner(max_items=2, max_text_chars=20)
    requests = [
        EmbeddingRequest(item_id=uuid.uuid4(), text="one"),
        EmbeddingRequest(item_id=uuid.uuid4(), text="two"),
        EmbeddingRequest(item_id=uuid.uuid4(), text="three"),
    ]

    assert [len(batch) for batch in planner.batches(requests)] == [2, 1]
    with pytest.raises(ValidationError):
        planner.batches([EmbeddingRequest(item_id=uuid.uuid4(), text="")])
