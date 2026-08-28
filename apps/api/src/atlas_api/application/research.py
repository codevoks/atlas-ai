from __future__ import annotations

import hashlib
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter

from atlas_api.application.ports import (
    ResearchBudget,
    ResearchStepDraft,
    SearchCandidate,
    ToolInvocationDraft,
)
from atlas_api.domain.errors import ResourceExhaustedError, ValidationError
from atlas_api.domain.models import ResearchStepStatus, ToolInvocationStatus

RESEARCH_GRAPH_VERSION = "phase9-bounded-research-graph-v1"
RESEARCH_CONFIG_VERSION = "phase9-deterministic-local-research-v1"
RESEARCH_CHECKPOINT_SCHEMA_VERSION = "phase9-research-state-v1"
RESEARCH_PROMPT_VERSION = "phase9-cited-report-v1"

ALLOWED_RESEARCH_TOOLS = frozenset({"atlas_retrieval", "local_policy_catalog"})
FORBIDDEN_TOOL_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(shell|terminal|bash|python|node|browser|curl|wget)\b",
        r"\b(delete|drop|truncate|exfiltrate|leak|secret|password|api[_ -]?key)\b",
        r"\bhttps?://|file://|ftp://|localhost|127\.0\.0\.1|169\.254\.169\.254\b",
        r"ignore (previous|all|system|developer) instructions",
    )
)


@dataclass(frozen=True, slots=True)
class PlannedQuestion:
    ordinal: int
    query: str
    rationale: str


@dataclass(frozen=True, slots=True)
class ResearchGraphOutput:
    state: dict[str, object]
    usage: dict[str, object]
    evidence: list[dict[str, object]]
    warnings: list[str]
    steps: list[ResearchStepDraft]
    tool_invocations: list[ToolInvocationDraft]
    needs_approval: bool
    approval_payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class ResearchSynthesisOutput:
    report_text: str
    usage: dict[str, object]
    warnings: list[str]
    steps: list[ResearchStepDraft]


class ResearchBudgetLedger:
    def __init__(self, budget: ResearchBudget) -> None:
        self._budget = budget
        self._steps = 0
        self._tool_calls = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._cost_usd = 0.0

    def reserve_step(self, node_name: str) -> None:
        if self._steps + 1 > self._budget.max_steps:
            raise ResourceExhaustedError(
                "Research step budget exhausted.", details={"node": node_name}
            )
        self._steps += 1

    def reserve_tool_call(self, tool_name: str) -> None:
        if self._tool_calls + 1 > self._budget.max_tool_calls:
            raise ResourceExhaustedError(
                "Research tool-call budget exhausted.", details={"tool": tool_name}
            )
        self._tool_calls += 1

    def commit_tokens(self, *, input_tokens: int, output_tokens: int) -> None:
        if self._input_tokens + input_tokens > self._budget.max_input_tokens:
            raise ResourceExhaustedError("Research input-token budget exhausted.")
        if self._output_tokens + output_tokens > self._budget.max_output_tokens:
            raise ResourceExhaustedError("Research output-token budget exhausted.")
        self._input_tokens += input_tokens
        self._output_tokens += output_tokens

    def usage(self) -> dict[str, object]:
        return {
            "steps": self._steps,
            "tool_calls": self._tool_calls,
            "input_tokens": self._input_tokens,
            "output_tokens": self._output_tokens,
            "cost_usd": round(self._cost_usd, 6),
            "paid_services": False,
        }


class ToolPolicy:
    def validate_question(self, text: str) -> list[str]:
        warnings: list[str] = []
        for pattern in FORBIDDEN_TOOL_PATTERNS:
            if pattern.search(text):
                raise ValidationError("Research question requested a forbidden tool or boundary.")
        if len(text) > 1200:
            raise ValidationError("Research question exceeds the configured length limit.")
        return warnings

    def authorize_tool(self, tool_name: str, payload: dict[str, object]) -> None:
        if tool_name not in ALLOWED_RESEARCH_TOOLS:
            raise ValidationError("Research tool is not allowlisted.")
        serialized = str(payload)
        for pattern in FORBIDDEN_TOOL_PATTERNS:
            if pattern.search(serialized):
                raise ValidationError("Research tool input failed policy validation.")


class DeterministicPlanner:
    def plan(self, question: str) -> list[PlannedQuestion]:
        clean = " ".join(question.split())
        if not clean:
            raise ValidationError("Research question must not be empty.")
        focused = clean.rstrip("?.!")
        return [
            PlannedQuestion(
                ordinal=1,
                query=focused,
                rationale="Retrieve directly relevant Atlas evidence for the user question.",
            ),
            PlannedQuestion(
                ordinal=2,
                query=f"{focused} policy risk controls",
                rationale="Check whether governance, risk, or control evidence changes the report.",
            ),
        ]


class LocalPolicyCatalogTool:
    name = "local_policy_catalog"

    def invoke(self, question: str) -> dict[str, object]:
        lowered = question.lower()
        if "invoice" in lowered or "finance" in lowered or "approval" in lowered:
            guidance = (
                "Finance-sensitive conclusions require explicit approval before final synthesis."
            )
        else:
            guidance = "Use Atlas evidence only and preserve citation provenance."
        return {
            "source": "deterministic-local-policy-catalog",
            "guidance": guidance,
            "requires_approval": True,
            "external_network": False,
            "paid_services": False,
        }


class DeterministicResearchGraph:
    def __init__(self) -> None:
        self._planner = DeterministicPlanner()
        self._policy = ToolPolicy()
        self._catalog = LocalPolicyCatalogTool()

    def validate_question(self, question: str) -> None:
        self._policy.validate_question(question)

    async def run_until_approval(
        self,
        *,
        question: str,
        budget: ResearchBudget,
        retrieval: Callable[[str], Awaitable[list[SearchCandidate]]],
    ) -> ResearchGraphOutput:
        ledger = ResearchBudgetLedger(budget)
        warnings = self._policy.validate_question(question)
        steps: list[ResearchStepDraft] = []
        invocations: list[ToolInvocationDraft] = []
        evidence: list[dict[str, object]] = []

        start = perf_counter()
        ledger.reserve_step("plan")
        planned = self._planner.plan(question)
        ledger.commit_tokens(input_tokens=_token_count(question), output_tokens=len(planned) * 8)
        steps.append(
            ResearchStepDraft(
                ordinal=1,
                node_name="plan",
                status=ResearchStepStatus.SUCCEEDED,
                input_summary={"question_hash": _hash_text(question)},
                output_summary={
                    "planned_questions": [
                        {"ordinal": item.ordinal, "query": item.query, "rationale": item.rationale}
                        for item in planned
                    ],
                    "planner": "deterministic-local",
                },
                latency_ms=_elapsed_ms(start),
            )
        )

        retrieve_start = perf_counter()
        ledger.reserve_step("retrieve_atlas_evidence")
        for item in planned:
            ledger.reserve_tool_call("atlas_retrieval")
            self._policy.authorize_tool(
                "atlas_retrieval", {"query": item.query, "planned_question": item.ordinal}
            )
            candidates = await retrieval(item.query)
            invocations.append(
                ToolInvocationDraft(
                    step_ordinal=2,
                    tool_name="atlas_retrieval",
                    status=ToolInvocationStatus.SUCCEEDED,
                    input_summary={
                        "planned_question": item.ordinal,
                        "query_hash": _hash_text(item.query),
                        "top_k": 3,
                    },
                    output_summary={"candidate_count": len(candidates)},
                    idempotency_key=f"atlas-retrieval:{item.ordinal}:{_hash_text(item.query)}",
                    latency_ms=0,
                )
            )
            for candidate in candidates:
                evidence.append(_candidate_evidence(candidate, item))
        evidence = _dedupe_evidence(evidence)
        ledger.commit_tokens(
            input_tokens=sum(_token_count(item.query) for item in planned),
            output_tokens=sum(_token_count(str(item.get("quote", ""))) for item in evidence),
        )
        steps.append(
            ResearchStepDraft(
                ordinal=2,
                node_name="retrieve_atlas_evidence",
                status=ResearchStepStatus.SUCCEEDED,
                input_summary={"planned_question_count": len(planned)},
                output_summary={
                    "evidence_count": len(evidence),
                    "tool": "atlas_retrieval",
                    "tenant_scoped": True,
                },
                latency_ms=_elapsed_ms(retrieve_start),
            )
        )

        catalog_start = perf_counter()
        ledger.reserve_step("local_policy_check")
        ledger.reserve_tool_call(self._catalog.name)
        self._policy.authorize_tool(self._catalog.name, {"question_hash": _hash_text(question)})
        catalog = self._catalog.invoke(question)
        invocations.append(
            ToolInvocationDraft(
                step_ordinal=3,
                tool_name=self._catalog.name,
                status=ToolInvocationStatus.SUCCEEDED,
                input_summary={"question_hash": _hash_text(question)},
                output_summary=catalog,
                idempotency_key=f"local-policy:{_hash_text(question)}",
                latency_ms=_elapsed_ms(catalog_start),
            )
        )
        steps.append(
            ResearchStepDraft(
                ordinal=3,
                node_name="local_policy_check",
                status=ResearchStepStatus.SUCCEEDED,
                input_summary={"question_hash": _hash_text(question)},
                output_summary=catalog,
                latency_ms=_elapsed_ms(catalog_start),
            )
        )

        approval_payload = {
            "approval_boundary": "synthesize_cited_report",
            "reason": (
                "Final research synthesis is gated so a human can inspect evidence and "
                "tool provenance first."
            ),
            "planned_questions": [item.query for item in planned],
            "evidence_count": len(evidence),
            "tool_names": sorted(ALLOWED_RESEARCH_TOOLS),
            "paid_services": False,
        }
        ledger.reserve_step("await_human_approval")
        steps.append(
            ResearchStepDraft(
                ordinal=4,
                node_name="await_human_approval",
                status=ResearchStepStatus.SUCCEEDED,
                input_summary={"approval_boundary": "synthesize_cited_report"},
                output_summary=approval_payload,
                latency_ms=0,
            )
        )

        state: dict[str, object] = {
            "schema_version": RESEARCH_CHECKPOINT_SCHEMA_VERSION,
            "graph_version": RESEARCH_GRAPH_VERSION,
            "question_hash": _hash_text(question),
            "planned_questions": [item.query for item in planned],
            "evidence": evidence,
            "approval_payload": approval_payload,
            "next_node": "synthesize_report",
        }
        return ResearchGraphOutput(
            state=state,
            usage=ledger.usage(),
            evidence=evidence,
            warnings=sorted(set(warnings)),
            steps=steps,
            tool_invocations=invocations,
            needs_approval=True,
            approval_payload=approval_payload,
        )

    def synthesize_after_approval(
        self,
        *,
        question: str,
        checkpoint_state: dict[str, object],
        existing_usage: dict[str, object],
        budget: ResearchBudget,
    ) -> ResearchSynthesisOutput:
        ledger = ResearchBudgetLedger(budget)
        for _ in range(_int_value(existing_usage.get("steps"), default=0)):
            ledger.reserve_step("replayed_checkpoint_step")
        for _ in range(_int_value(existing_usage.get("tool_calls"), default=0)):
            ledger.reserve_tool_call("replayed_checkpoint_tool")
        ledger.commit_tokens(
            input_tokens=_int_value(existing_usage.get("input_tokens"), default=0),
            output_tokens=_int_value(existing_usage.get("output_tokens"), default=0),
        )

        start = perf_counter()
        ledger.reserve_step("synthesize_report")
        evidence_value = checkpoint_state.get("evidence")
        evidence = (
            [item for item in evidence_value if isinstance(item, dict)]
            if isinstance(evidence_value, list)
            else []
        )
        if not evidence:
            report = (
                "# Research report\n\n"
                "No tenant-authorized evidence was retrieved, so Atlas cannot produce a cited "
                "research conclusion."
            )
            warnings = ["no_evidence"]
        else:
            bullets = []
            for index, item in enumerate(evidence[:3], start=1):
                quote = str(item.get("quote", "")).strip()
                title = str(item.get("document_title", "Untitled"))
                bullets.append(f"- {quote} [{index}]")
                item["citation_marker"] = f"[{index}]"
                item["document_title"] = title
            citations = "\n".join(
                f"[{index}] {item.get('document_title')} · chunk {item.get('chunk_id')}"
                for index, item in enumerate(evidence[:3], start=1)
            )
            report = (
                "# Research report\n\n"
                f"Question: {question}\n\n"
                "## Findings\n"
                + "\n".join(bullets)
                + "\n\n## Citations\n"
                + citations
                + (
                    "\n\nThis report used only tenant-authorized Atlas evidence and "
                    "deterministic local tools."
                )
            )
            warnings = []
        ledger.commit_tokens(
            input_tokens=sum(_token_count(str(item.get("quote", ""))) for item in evidence),
            output_tokens=_token_count(report),
        )
        return ResearchSynthesisOutput(
            report_text=report,
            usage=ledger.usage(),
            warnings=warnings,
            steps=[
                ResearchStepDraft(
                    ordinal=5,
                    node_name="synthesize_report",
                    status=ResearchStepStatus.SUCCEEDED,
                    input_summary={"evidence_count": len(evidence)},
                    output_summary={
                        "citation_count": min(len(evidence), 3),
                        "prompt_version": RESEARCH_PROMPT_VERSION,
                        "paid_services": False,
                    },
                    latency_ms=_elapsed_ms(start),
                )
            ],
        )


def default_research_budget() -> ResearchBudget:
    return ResearchBudget(
        max_steps=8,
        max_tool_calls=4,
        max_input_tokens=4000,
        max_output_tokens=2000,
        max_cost_usd=0.0,
        max_wall_time_ms=30_000,
    )


def _candidate_evidence(candidate: SearchCandidate, planned: PlannedQuestion) -> dict[str, object]:
    return {
        "chunk_id": str(candidate.chunk_id),
        "document_id": str(candidate.document_id),
        "document_version_id": str(candidate.document_version_id),
        "source_id": str(candidate.source_id),
        "document_title": candidate.document_title,
        "quote": candidate.snippet,
        "retrieval_stage": candidate.retrieval_stage,
        "retrieval_score": candidate.score,
        "planned_question": planned.query,
        "planned_question_ordinal": planned.ordinal,
        "tool_name": "atlas_retrieval",
        "retrieval_provenance": candidate.retrieval_provenance or {},
    }


def _dedupe_evidence(items: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    output: list[dict[str, object]] = []
    for item in items:
        key = str(item["chunk_id"])
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output[:5]


def _token_count(text: str) -> int:
    return len([part for part in text.split() if part])


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _int_value(value: object, *, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default


def _elapsed_ms(start: float) -> int:
    return max(0, int((perf_counter() - start) * 1000))
