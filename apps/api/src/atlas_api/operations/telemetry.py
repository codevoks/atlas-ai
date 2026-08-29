from __future__ import annotations

import time
import uuid
from collections import Counter, deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from threading import Lock

from atlas_api.config import Settings

TELEMETRY_SCHEMA_VERSION = "phase11-local-telemetry-v1"
OPERATIONS_POSTURE_VERSION = "phase11-production-hardening-v1"


@dataclass(frozen=True, slots=True)
class RequestTrace:
    trace_id: str
    request_id: str
    method: str
    route: str
    status_code: int
    duration_ms: float
    recorded_at_unix_ms: int


@dataclass(frozen=True, slots=True)
class RouteMetric:
    route: str
    method: str
    count: int
    error_count: int
    p95_ms: float
    max_ms: float


@dataclass(frozen=True, slots=True)
class TelemetrySnapshot:
    schema_version: str
    exporter: str
    content_capture_enabled: bool
    retained_trace_count: int
    dropped_trace_count: int
    routes: list[RouteMetric]


class LocalTelemetry:
    """Bounded in-memory telemetry sink for zero-cost local validation.

    The sink intentionally records route templates and timing/status metadata only. It never records
    request bodies, response bodies, prompts, document text, or provider payloads.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = Lock()
        self._traces: deque[RequestTrace] = deque(maxlen=settings.telemetry_buffer_size)
        self._dropped = 0

    def start_trace_id(self) -> str:
        return str(uuid.uuid4())

    def record_request(
        self,
        *,
        trace_id: str,
        request_id: str,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        if not self._settings.telemetry_enabled or self._settings.telemetry_exporter == "none":
            return
        trace = RequestTrace(
            trace_id=trace_id,
            request_id=request_id,
            method=method,
            route=route,
            status_code=status_code,
            duration_ms=round(duration_ms, 3),
            recorded_at_unix_ms=int(time.time() * 1000),
        )
        with self._lock:
            if len(self._traces) == self._traces.maxlen:
                self._dropped += 1
            self._traces.append(trace)

    def snapshot(self) -> TelemetrySnapshot:
        with self._lock:
            traces = list(self._traces)
            dropped = self._dropped
        return TelemetrySnapshot(
            schema_version=TELEMETRY_SCHEMA_VERSION,
            exporter=self._settings.telemetry_exporter,
            content_capture_enabled=self._settings.telemetry_capture_content,
            retained_trace_count=len(traces),
            dropped_trace_count=dropped,
            routes=_route_metrics(traces),
        )


def route_template_from_scope(scope: Mapping[str, object]) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    raw_path = scope.get("path")
    return raw_path if isinstance(raw_path, str) and raw_path else "unknown"


def _route_metrics(traces: Iterable[RequestTrace]) -> list[RouteMetric]:
    grouped: dict[tuple[str, str], list[RequestTrace]] = {}
    for trace in traces:
        grouped.setdefault((trace.route, trace.method), []).append(trace)
    metrics: list[RouteMetric] = []
    for (route, method), items in grouped.items():
        durations = sorted(item.duration_ms for item in items)
        error_count = sum(1 for item in items if item.status_code >= 500)
        metrics.append(
            RouteMetric(
                route=route,
                method=method,
                count=len(items),
                error_count=error_count,
                p95_ms=_percentile(durations, 0.95),
                max_ms=durations[-1],
            )
        )
    metrics.sort(key=lambda item: (item.route, item.method))
    return metrics


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    index = min(len(values) - 1, max(0, int(round((len(values) - 1) * percentile))))
    return round(values[index], 3)


def evaluate_slo_status(snapshot: TelemetrySnapshot, settings: Settings) -> dict[str, object]:
    route_counts = Counter(metric.route for metric in snapshot.routes)
    api_routes = [metric for metric in snapshot.routes if not metric.route.startswith("/health/")]
    worst_api_p95 = max((metric.p95_ms for metric in api_routes), default=0.0)
    worst_search_p95 = max(
        (metric.p95_ms for metric in snapshot.routes if "/search" in metric.route), default=0.0
    )
    worst_answer_p95 = max(
        (metric.p95_ms for metric in snapshot.routes if "/answers" in metric.route), default=0.0
    )
    worst_research_p95 = max(
        (metric.p95_ms for metric in snapshot.routes if "/research-runs" in metric.route),
        default=0.0,
    )
    total = sum(metric.count for metric in snapshot.routes)
    errors = sum(metric.error_count for metric in snapshot.routes)
    return {
        "schema_version": "phase11-slo-summary-v1",
        "request_count": total,
        "route_count": len(route_counts),
        "error_count": errors,
        "error_rate": round(errors / total, 6) if total else 0.0,
        "objectives": {
            "api_p95_ms": settings.ops_slo_api_p95_ms,
            "search_p95_ms": settings.ops_slo_search_p95_ms,
            "answer_p95_ms": settings.ops_slo_answer_p95_ms,
            "research_resume_p95_ms": settings.ops_slo_research_resume_p95_ms,
        },
        "observed": {
            "api_p95_ms": worst_api_p95,
            "search_p95_ms": worst_search_p95,
            "answer_p95_ms": worst_answer_p95,
            "research_resume_p95_ms": worst_research_p95,
        },
        "within_objective": {
            "api": worst_api_p95 <= settings.ops_slo_api_p95_ms,
            "search": worst_search_p95 <= settings.ops_slo_search_p95_ms,
            "answer": worst_answer_p95 <= settings.ops_slo_answer_p95_ms,
            "research_resume": worst_research_p95 <= settings.ops_slo_research_resume_p95_ms,
        },
    }
