from __future__ import annotations

import uuid
from dataclasses import dataclass
from math import log2


@dataclass(frozen=True, slots=True)
class RetrievalModeMetrics:
    mode: str
    recall_at_k: float
    reciprocal_rank: float
    precision_at_k: float
    ndcg_at_k: float


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
                precision_at_k=len(hits) / k,
                reciprocal_rank=reciprocal_rank,
                ndcg_at_k=ndcg_at_k(relevant_chunk_ids=relevant_chunk_ids, ranked_ids=window, k=k),
            )
        )
    return results


def recall_at_k(
    *, relevant_chunk_ids: set[uuid.UUID], ranked_ids: list[uuid.UUID], k: int
) -> float:
    _validate_metric_inputs(relevant_chunk_ids, k)
    return len(relevant_chunk_ids.intersection(ranked_ids[:k])) / len(relevant_chunk_ids)


def precision_at_k(
    *, relevant_chunk_ids: set[uuid.UUID], ranked_ids: list[uuid.UUID], k: int
) -> float:
    _validate_metric_inputs(relevant_chunk_ids, k)
    return len(relevant_chunk_ids.intersection(ranked_ids[:k])) / k


def reciprocal_rank(
    *, relevant_chunk_ids: set[uuid.UUID], ranked_ids: list[uuid.UUID], k: int
) -> float:
    _validate_metric_inputs(relevant_chunk_ids, k)
    for rank, chunk_id in enumerate(ranked_ids[:k], start=1):
        if chunk_id in relevant_chunk_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(*, relevant_chunk_ids: set[uuid.UUID], ranked_ids: list[uuid.UUID], k: int) -> float:
    _validate_metric_inputs(relevant_chunk_ids, k)
    dcg = 0.0
    for rank, chunk_id in enumerate(ranked_ids[:k], start=1):
        if chunk_id in relevant_chunk_ids:
            dcg += 1.0 / log2(rank + 1)
    ideal_hits = min(len(relevant_chunk_ids), k)
    ideal_dcg = sum(1.0 / log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / ideal_dcg if ideal_dcg else 0.0


def substring_coverage(*, expected_substrings: list[str], text: str) -> float:
    normalized_text = text.lower()
    expected = [item.strip().lower() for item in expected_substrings if item.strip()]
    if not expected:
        return 1.0
    hits = sum(1 for item in expected if item in normalized_text)
    return hits / len(expected)


def citation_quote_coverage(*, expected_quotes: list[str], actual_quotes: list[str]) -> float:
    normalized_actual = [item.strip().lower() for item in actual_quotes if item.strip()]
    expected = [item.strip().lower() for item in expected_quotes if item.strip()]
    if not expected:
        return 1.0
    hits = 0
    for quote in expected:
        if any(quote in actual for actual in normalized_actual):
            hits += 1
    return hits / len(expected)


def citation_verified_rate(statuses: list[str]) -> float:
    if not statuses:
        return 0.0
    return sum(1 for status in statuses if status == "verified") / len(statuses)


def _validate_metric_inputs(relevant_chunk_ids: set[uuid.UUID], k: int) -> None:
    if k < 1:
        raise ValueError("k must be positive")
    if not relevant_chunk_ids:
        raise ValueError("at least one relevant chunk id is required")
