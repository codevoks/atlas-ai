from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from atlas_api.domain.errors import ValidationError

BASELINE_RETRIEVAL_CONFIG = "phase5-postgres-fts-rrf-v1"
ADVANCED_RETRIEVAL_CONFIG = "phase8-multi-query-expansion-v1"
SUPPORTED_RETRIEVAL_CONFIGS = frozenset({BASELINE_RETRIEVAL_CONFIG, ADVANCED_RETRIEVAL_CONFIG})

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

EXPANSION_TERMS: dict[str, tuple[str, ...]] = {
    "accounts": ("finance", "invoice"),
    "auth": ("authentication", "identity", "saml"),
    "authorization": ("approval", "access"),
    "bill": ("invoice", "payment"),
    "billing": ("invoice", "payment"),
    "expense": ("invoice", "finance"),
    "finance": ("accounts", "invoice", "payment"),
    "identity": ("saml", "access", "authentication"),
    "invoice": ("payment", "finance", "approval"),
    "invoices": ("payment", "finance", "approval"),
    "pay": ("payment", "invoice"),
    "payment": ("invoice", "approval", "finance"),
    "review": ("approval", "queue"),
    "sso": ("saml", "identity", "authentication"),
    "vendor": ("supplier", "invoice"),
}

INJECTION_PATTERNS = (
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "developer message",
    "reveal secret",
    "exfiltrate",
    "bypass policy",
)


@dataclass(frozen=True, slots=True)
class RetrievalConfig:
    version: str
    max_query_variants: int
    max_total_branch_queries: int
    max_candidates_per_branch: int
    transformation_policy: Literal["identity", "deterministic_synonym_expansion"]
    diversity_enabled: bool


@dataclass(frozen=True, slots=True)
class QueryVariant:
    text: str
    rank: int
    transform: Literal["original", "deterministic_expansion"]


@dataclass(frozen=True, slots=True)
class RetrievalPlan:
    original_query: str
    config: RetrievalConfig
    variants: list[QueryVariant]
    warnings: list[str]

    @property
    def branch_budget(self) -> dict[str, object]:
        return {
            "max_query_variants": self.config.max_query_variants,
            "max_total_branch_queries": self.config.max_total_branch_queries,
            "max_candidates_per_branch": self.config.max_candidates_per_branch,
            "actual_query_variants": len(self.variants),
        }


BASELINE_CONFIG = RetrievalConfig(
    version=BASELINE_RETRIEVAL_CONFIG,
    max_query_variants=1,
    max_total_branch_queries=2,
    max_candidates_per_branch=20,
    transformation_policy="identity",
    diversity_enabled=False,
)

ADVANCED_CONFIG = RetrievalConfig(
    version=ADVANCED_RETRIEVAL_CONFIG,
    max_query_variants=3,
    max_total_branch_queries=6,
    max_candidates_per_branch=8,
    transformation_policy="deterministic_synonym_expansion",
    diversity_enabled=True,
)


class DeterministicQueryTransformer:
    def plan(self, *, query: str, retrieval_config_version: str | None) -> RetrievalPlan:
        clean_query = " ".join(query.split())
        if not clean_query:
            raise ValidationError("Search query must not be empty.")
        config = retrieval_config(retrieval_config_version)
        if config.transformation_policy == "identity":
            return RetrievalPlan(
                original_query=clean_query,
                config=config,
                variants=[QueryVariant(text=clean_query, rank=1, transform="original")],
                warnings=[],
            )

        variants = [QueryVariant(text=clean_query, rank=1, transform="original")]
        warnings: list[str] = []
        if _contains_injection_like_text(clean_query):
            warnings.append("query_expansion_suppressed_for_injection_like_text")
            return RetrievalPlan(
                original_query=clean_query,
                config=config,
                variants=variants,
                warnings=warnings,
            )

        expanded = self._expanded_query(clean_query)
        if expanded and expanded != clean_query.lower():
            variants.append(
                QueryVariant(
                    text=expanded,
                    rank=len(variants) + 1,
                    transform="deterministic_expansion",
                )
            )

        if len(variants) < config.max_query_variants:
            focused = self._focused_query(clean_query)
            existing = {variant.text.lower() for variant in variants}
            if focused and focused.lower() not in existing:
                variants.append(
                    QueryVariant(
                        text=focused,
                        rank=len(variants) + 1,
                        transform="deterministic_expansion",
                    )
                )

        return RetrievalPlan(
            original_query=clean_query,
            config=config,
            variants=variants[: config.max_query_variants],
            warnings=warnings,
        )

    def _expanded_query(self, query: str) -> str | None:
        tokens = TOKEN_PATTERN.findall(query.lower())
        additions: list[str] = []
        seen = set(tokens)
        for token in tokens:
            for term in EXPANSION_TERMS.get(token, ()):
                if term not in seen:
                    additions.append(term)
                    seen.add(term)
        if not additions:
            return None
        return " ".join([*tokens, *additions[:8]])

    def _focused_query(self, query: str) -> str | None:
        tokens = TOKEN_PATTERN.findall(query.lower())
        focus = [
            term
            for token in tokens
            for term in EXPANSION_TERMS.get(token, ())
            if term not in tokens
        ]
        if not focus:
            return None
        return " ".join(dict.fromkeys(focus[:6]))


def retrieval_config(version: str | None) -> RetrievalConfig:
    selected = version or BASELINE_RETRIEVAL_CONFIG
    if selected == BASELINE_RETRIEVAL_CONFIG:
        return BASELINE_CONFIG
    if selected == ADVANCED_RETRIEVAL_CONFIG:
        return ADVANCED_CONFIG
    raise ValidationError("The requested retrieval configuration is not supported.")


def _contains_injection_like_text(query: str) -> bool:
    lowered = query.lower()
    return any(pattern in lowered for pattern in INJECTION_PATTERNS)
