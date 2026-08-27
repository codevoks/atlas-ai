from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass

from atlas_api.application.ports import (
    AnswerEvidenceDraft,
    CitationDraft,
    SearchCandidate,
    ValidatedCitationRecord,
)
from atlas_api.config import Settings
from atlas_api.domain.errors import ValidationError
from atlas_api.domain.models import CitationValidationStatus

INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "reveal secrets",
    "exfiltrate",
    "system prompt",
    "developer message",
)


@dataclass(frozen=True, slots=True)
class ContextPackage:
    evidence: list[AnswerEvidenceDraft]
    input_tokens: int
    warnings: list[str]


@dataclass(frozen=True, slots=True)
class StructuredAnswer:
    text: str
    citations: list[CitationDraft]
    warnings: list[str]
    output_tokens: int
    latency_ms: int


class DeterministicReranker:
    provider = "deterministic-local"
    model = "atlas-local-reranker"
    model_version = "2026-08-28"

    def rerank(self, candidates: list[SearchCandidate]) -> list[SearchCandidate]:
        return sorted(
            candidates,
            key=lambda item: (
                item.lexical_rank is None,
                item.semantic_rank is None,
                item.lexical_rank or 9999,
                item.semantic_rank or 9999,
                -item.score,
                item.chunk_id.hex,
            ),
        )


class ContextBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, candidates: list[SearchCandidate]) -> ContextPackage:
        if not candidates:
            return ContextPackage(evidence=[], input_tokens=0, warnings=["no_evidence"])

        warnings: list[str] = []
        evidence: list[AnswerEvidenceDraft] = []
        remaining_chars = self._settings.answer_max_context_chars
        for candidate in candidates[: self._settings.answer_max_context_items]:
            if remaining_chars <= 0:
                warnings.append("context_budget_exhausted")
                break
            text = candidate.text.strip()
            if not text:
                continue
            if _contains_injection(text):
                warnings.append("untrusted_instruction_detected")
            context_text = text[:remaining_chars]
            evidence.append(
                AnswerEvidenceDraft(
                    candidate=candidate,
                    rank=len(evidence) + 1,
                    context_text=context_text,
                )
            )
            remaining_chars -= len(context_text)
        return ContextPackage(
            evidence=evidence,
            input_tokens=sum(_count_tokens(item.context_text) for item in evidence),
            warnings=sorted(set(warnings)),
        )


class DeterministicLocalGenerator:
    provider = "deterministic-local"

    def __init__(self, settings: Settings) -> None:
        self.model = settings.answer_model
        self.model_version = settings.answer_model_version
        self.prompt_version = settings.answer_prompt_version
        self._settings = settings

    def generate(self, *, query: str, context: ContextPackage) -> StructuredAnswer:
        started = time.perf_counter()
        if not context.evidence:
            text = "I do not have enough retrieved evidence to answer this question."
            return StructuredAnswer(
                text=text,
                citations=[],
                warnings=sorted(set([*context.warnings, "evidence_only_refusal"])),
                output_tokens=_count_tokens(text),
                latency_ms=_elapsed_ms(started),
            )

        first = context.evidence[0]
        quote = _select_quote(first.context_text)
        answer = (
            f"Based on the retrieved evidence, {quote} [1] "
            "This answer is limited to the cited workspace evidence."
        )
        if len(answer) > self._settings.answer_max_output_chars:
            answer = answer[: self._settings.answer_max_output_chars].rstrip()
        marker_start = answer.find("[1]")
        citation = CitationDraft(
            marker="[1]",
            evidence_rank=first.rank,
            quote=quote,
            answer_start_char=marker_start,
            answer_end_char=marker_start + 3,
        )
        return StructuredAnswer(
            text=answer,
            citations=[citation],
            warnings=context.warnings,
            output_tokens=_count_tokens(answer),
            latency_ms=_elapsed_ms(started),
        )


class CitationValidator:
    def validate(
        self,
        *,
        answer_text: str,
        evidence: list[AnswerEvidenceDraft],
        citations: list[CitationDraft],
    ) -> list[ValidatedCitationRecord]:
        evidence_by_rank = {item.rank: item for item in evidence}
        validated: list[ValidatedCitationRecord] = []
        for citation in citations:
            evidence_item = evidence_by_rank.get(citation.evidence_rank)
            if evidence_item is None:
                raise ValidationError("Citation references evidence that was not supplied.")
            answer_marker = answer_text[citation.answer_start_char : citation.answer_end_char]
            evidence_offset = evidence_item.context_text.find(citation.quote)
            if answer_marker != citation.marker or evidence_offset < 0:
                raise ValidationError("Citation could not be validated against supplied evidence.")
            candidate = evidence_item.candidate
            validated.append(
                ValidatedCitationRecord(
                    id=uuid.uuid4(),
                    marker=citation.marker,
                    evidence_rank=evidence_item.rank,
                    answer_evidence_id=uuid.uuid4(),
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    document_version_id=candidate.document_version_id,
                    quote=citation.quote,
                    evidence_start_char=candidate.start_char + evidence_offset,
                    evidence_end_char=candidate.start_char + evidence_offset + len(citation.quote),
                    answer_start_char=citation.answer_start_char,
                    answer_end_char=citation.answer_end_char,
                    status=CitationValidationStatus.VERIFIED,
                )
            )
        return validated


def _select_quote(text: str) -> str:
    paragraphs = [item.strip() for item in re.split(r"\n{2,}", text) if item.strip()]
    candidates: list[str] = []
    for paragraph in paragraphs:
        if paragraph.startswith("#"):
            continue
        sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", paragraph) if item.strip()]
        candidates.extend(sentences or [paragraph])
    if not candidates:
        candidates = [item.strip() for item in text.splitlines() if item.strip()]
    if not candidates:
        return ""
    safe_sentences = [item for item in candidates[:5] if not _contains_injection(item)]
    selected = max(safe_sentences or candidates[:3], key=lambda item: len(item))
    return selected[:240]


def _contains_injection(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in INJECTION_PATTERNS)


def _count_tokens(text: str) -> int:
    return len([token for token in re.split(r"\s+", text.strip()) if token])


def _elapsed_ms(started: float) -> int:
    return max(int((time.perf_counter() - started) * 1000), 0)
