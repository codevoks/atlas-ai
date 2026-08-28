from __future__ import annotations

import shutil
import subprocess
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from atlas_api.application.ports import (
    EvaluationCaseRecord,
    EvaluationResultRecord,
    SearchFilter,
)
from atlas_api.application.retrieval_metrics import (
    citation_quote_coverage,
    citation_verified_rate,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    substring_coverage,
)
from atlas_api.domain.errors import DomainError
from atlas_api.domain.models import Actor, EvaluationResultStatus

METRIC_VERSIONS = {
    "recall_at_k": "phase7-deterministic-v1",
    "precision_at_k": "phase7-deterministic-v1",
    "mrr": "phase7-deterministic-v1",
    "ndcg_at_k": "phase7-deterministic-v1",
    "answer_substring_coverage": "phase7-deterministic-v1",
    "citation_quote_coverage": "phase7-deterministic-v1",
    "citation_verified_rate": "phase7-deterministic-v1",
}


@dataclass(frozen=True, slots=True)
class EvaluationCaseExecution:
    status: EvaluationResultStatus
    metrics: dict[str, object]
    retrieved_chunk_ids: list[uuid.UUID]
    answer_run_id: uuid.UUID | None
    error_code: str | None
    error_message: str | None
    latency_ms: int
    total_cost_usd: float


class DeterministicEvaluationRunner:
    def __init__(self, search_service: Any, answer_service: Any) -> None:
        self._search = search_service
        self._answer = answer_service

    async def run_case(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        case: EvaluationCaseRecord,
    ) -> EvaluationCaseExecution:
        started = time.perf_counter()
        try:
            relevant = set(case.relevant_chunk_ids)
            if not relevant:
                return EvaluationCaseExecution(
                    status=EvaluationResultStatus.MISSING_LABELS,
                    metrics={"error": "missing_relevant_chunk_ids"},
                    retrieved_chunk_ids=[],
                    answer_run_id=None,
                    error_code="missing_labels",
                    error_message="The evaluation case has no relevant chunk labels.",
                    latency_ms=_elapsed_ms(started),
                    total_cost_usd=0.0,
                )

            candidates, _debug = await self._search.search(
                actor=actor,
                workspace_id=workspace_id,
                query=case.query,
                top_k=case.top_k,
                filters=SearchFilter(),
                mode=case.retrieval_mode,
            )
            ranked_ids = [candidate.chunk_id for candidate in candidates]
            answer = await self._answer.answer(
                actor=actor,
                workspace_id=workspace_id,
                query=case.query,
                top_k=case.top_k,
                filters=SearchFilter(),
                retrieval_mode=case.retrieval_mode,
            )
            metrics: dict[str, object] = {
                "retrieval": {
                    "recall_at_k": recall_at_k(
                        relevant_chunk_ids=relevant, ranked_ids=ranked_ids, k=case.top_k
                    ),
                    "precision_at_k": precision_at_k(
                        relevant_chunk_ids=relevant, ranked_ids=ranked_ids, k=case.top_k
                    ),
                    "mrr": reciprocal_rank(
                        relevant_chunk_ids=relevant, ranked_ids=ranked_ids, k=case.top_k
                    ),
                    "ndcg_at_k": ndcg_at_k(
                        relevant_chunk_ids=relevant, ranked_ids=ranked_ids, k=case.top_k
                    ),
                },
                "answer": {
                    "answer_substring_coverage": substring_coverage(
                        expected_substrings=case.expected_answer_substrings,
                        text=answer.answer_text,
                    ),
                    "citation_quote_coverage": citation_quote_coverage(
                        expected_quotes=case.expected_citation_quotes,
                        actual_quotes=[citation.quote for citation in answer.citations],
                    ),
                    "citation_verified_rate": citation_verified_rate(
                        [citation.status.value for citation in answer.citations]
                    ),
                    "status": answer.status.value,
                    "grounding_status": answer.grounding_status,
                },
                "lineage": {
                    "retrieval_mode": case.retrieval_mode,
                    "top_k": case.top_k,
                    "answer_run_id": str(answer.id),
                },
            }
            return EvaluationCaseExecution(
                status=EvaluationResultStatus.SUCCEEDED,
                metrics=metrics,
                retrieved_chunk_ids=ranked_ids,
                answer_run_id=answer.id,
                error_code=None,
                error_message=None,
                latency_ms=_elapsed_ms(started),
                total_cost_usd=answer.total_cost_usd,
            )
        except DomainError as error:
            return EvaluationCaseExecution(
                status=EvaluationResultStatus.SYSTEM_FAILED,
                metrics={},
                retrieved_chunk_ids=[],
                answer_run_id=None,
                error_code=error.code,
                error_message=str(error),
                latency_ms=_elapsed_ms(started),
                total_cost_usd=0.0,
            )


def aggregate_results(
    cases: list[EvaluationCaseRecord],
    results: list[EvaluationResultRecord],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    successful = [result for result in results if result.status == EvaluationResultStatus.SUCCEEDED]
    aggregate = {
        "case_count": len(results),
        "succeeded": len(successful),
        "failed": len(results) - len(successful),
        "retrieval": _mean_nested(successful, "retrieval"),
        "answer": _mean_nested(successful, "answer"),
    }
    by_case_id = {case.id: case for case in cases}
    slice_groups: dict[str, list[EvaluationResultRecord]] = defaultdict(list)
    for result in successful:
        case = by_case_id.get(result.evaluation_case_id)
        if case is None:
            continue
        for slice_name in case.slices or ["default"]:
            slice_groups[slice_name].append(result)
    slice_metrics: dict[str, object] = {
        name: {
            "case_count": len(items),
            "retrieval": _mean_nested(items, "retrieval"),
            "answer": _mean_nested(items, "answer"),
        }
        for name, items in sorted(slice_groups.items())
    }
    failures: dict[str, int] = defaultdict(int)
    for result in results:
        if result.status != EvaluationResultStatus.SUCCEEDED:
            failures[result.status.value] += 1
    return aggregate, slice_metrics, dict(sorted(failures.items()))


def current_code_revision() -> str:
    try:
        git_path = shutil.which("git")
        if git_path is None:
            return "unknown"
        value = subprocess.check_output(  # noqa: S603 - fixed git executable and arguments
            [git_path, "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return value or "unknown"


def _mean_nested(results: list[EvaluationResultRecord], category: str) -> dict[str, float]:
    sums: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for result in results:
        raw = result.metrics.get(category)
        if not isinstance(raw, dict):
            continue
        for key, value in raw.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                sums[key] += float(value)
                counts[key] += 1
    return {
        key: round(sums[key] / counts[key], 6) for key in sorted(sums) if counts.get(key, 0) > 0
    }


def _elapsed_ms(started: float) -> int:
    return max(int((time.perf_counter() - started) * 1000), 0)
