from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Literal

from atlas_api.application.ports import SearchCandidate
from atlas_api.application.retrieval_metrics import compare_ranked_chunk_ids
from atlas_api.application.services import SemanticSearchService
from tests.support import make_settings


def candidate(
    chunk_id: uuid.UUID, *, score: float, stage: Literal["semantic", "lexical", "hybrid"]
) -> SearchCandidate:
    return SearchCandidate(
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        document_version_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        document_title="Runbook",
        ordinal=0,
        heading=None,
        block_type="section",
        start_char=0,
        end_char=10,
        snippet="Evidence snippet",
        distance=1.0 - score,
        score=score,
        retrieval_stage=stage,
        semantic_score=score if stage == "semantic" else None,
        lexical_score=score if stage == "lexical" else None,
    )


def test_rrf_fusion_deduplicates_chunk_version_identity_and_preserves_branch_provenance() -> None:
    service = SemanticSearchService(lambda: None, make_settings())  # type: ignore[arg-type]
    shared_chunk_id = uuid.uuid4()
    shared_version_id = uuid.uuid4()
    semantic = candidate(shared_chunk_id, score=0.91, stage="semantic")
    lexical = candidate(shared_chunk_id, score=0.42, stage="lexical")
    semantic = replace(semantic, document_version_id=shared_version_id)
    lexical = replace(lexical, document_version_id=shared_version_id)

    fused = service._fuse_rrf([semantic], [lexical], limit=5)

    assert len(fused) == 1
    assert fused[0].retrieval_stage == "hybrid"
    assert fused[0].semantic_rank == 1
    assert fused[0].lexical_rank == 1
    assert fused[0].semantic_score == 0.91
    assert fused[0].lexical_score == 0.42
    assert fused[0].rrf_score == round((1 / 61) + (1 / 61), 10)


def test_retrieval_metric_comparison_reports_recall_and_mrr_by_mode() -> None:
    relevant = {uuid.uuid4(), uuid.uuid4()}
    missed = uuid.uuid4()
    first, second = tuple(relevant)

    metrics = compare_ranked_chunk_ids(
        relevant_chunk_ids=relevant,
        ranked_by_mode={
            "semantic": [missed, first],
            "lexical": [first, second],
            "hybrid": [first, missed, second],
        },
        k=2,
    )

    by_mode = {item.mode: item for item in metrics}
    assert by_mode["lexical"].recall_at_k == 1.0
    assert by_mode["lexical"].reciprocal_rank == 1.0
    assert by_mode["semantic"].recall_at_k == 0.5
    assert by_mode["semantic"].reciprocal_rank == 0.5
    assert by_mode["hybrid"].recall_at_k == 0.5
    assert by_mode["hybrid"].reciprocal_rank == 1.0
