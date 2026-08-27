from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalModeMetrics:
    mode: str
    recall_at_k: float
    reciprocal_rank: float


def compare_ranked_chunk_ids(
    *,
    relevant_chunk_ids: set[uuid.UUID],
    ranked_by_mode: dict[str, list[uuid.UUID]],
    k: int,
) -> list[RetrievalModeMetrics]:
    if k < 1:
        raise ValueError("k must be positive")
    if not relevant_chunk_ids:
        raise ValueError("at least one relevant chunk id is required")

    results: list[RetrievalModeMetrics] = []
    for mode, ranked_ids in sorted(ranked_by_mode.items()):
        window = ranked_ids[:k]
        hits = relevant_chunk_ids.intersection(window)
        reciprocal_rank = 0.0
        for rank, chunk_id in enumerate(window, start=1):
            if chunk_id in relevant_chunk_ids:
                reciprocal_rank = 1.0 / rank
                break
        results.append(
            RetrievalModeMetrics(
                mode=mode,
                recall_at_k=len(hits) / len(relevant_chunk_ids),
                reciprocal_rank=reciprocal_rank,
            )
        )
    return results
