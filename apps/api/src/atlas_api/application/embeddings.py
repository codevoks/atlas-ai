from __future__ import annotations

import hashlib
import math
import re
import uuid
from dataclasses import dataclass
from typing import Protocol

from atlas_api.config import Settings
from atlas_api.domain.errors import IntegrityViolationError, ValidationError

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class EmbeddingRequest:
    item_id: uuid.UUID
    text: str


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    item_id: uuid.UUID
    vector: list[float]
    token_count: int


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    provider: str
    model: str
    model_version: str
    dimension: int
    normalized: bool
    items: list[EmbeddingResult]


class EmbeddingProvider(Protocol):
    provider: str
    model: str
    model_version: str
    dimension: int
    normalized: bool

    async def embed(self, requests: list[EmbeddingRequest]) -> EmbeddingBatch: ...


class EmbeddingBatchPlanner:
    def __init__(self, *, max_items: int, max_text_chars: int) -> None:
        if max_items < 1:
            raise ValidationError("Embedding batch size must be positive.")
        if max_text_chars < 1:
            raise ValidationError("Embedding text character limit must be positive.")
        self._max_items = max_items
        self._max_text_chars = max_text_chars

    def batches(self, requests: list[EmbeddingRequest]) -> list[list[EmbeddingRequest]]:
        for request in requests:
            if not request.text.strip():
                raise ValidationError("Embedding text must not be empty.")
            if len(request.text) > self._max_text_chars:
                raise ValidationError("Embedding text exceeded the configured maximum.")
        return [
            requests[index : index + self._max_items]
            for index in range(0, len(requests), self._max_items)
        ]


class DeterministicLocalEmbeddingProvider:
    normalized = True

    def __init__(self, settings: Settings) -> None:
        self.provider = settings.embedding_provider
        self.model = settings.embedding_model
        self.model_version = settings.embedding_model_version
        self.dimension = settings.embedding_dimension
        self._max_text_chars = settings.embedding_max_text_chars
        if self.provider != "deterministic-local":
            raise ValidationError("Only the deterministic-local embedding provider is enabled.")

    async def embed(self, requests: list[EmbeddingRequest]) -> EmbeddingBatch:
        return EmbeddingBatch(
            provider=self.provider,
            model=self.model,
            model_version=self.model_version,
            dimension=self.dimension,
            normalized=self.normalized,
            items=[self._embed_one(request) for request in requests],
        )

    def _embed_one(self, request: EmbeddingRequest) -> EmbeddingResult:
        text = request.text.strip()
        if not text:
            raise ValidationError("Embedding text must not be empty.")
        if len(text) > self._max_text_chars:
            raise ValidationError("Embedding text exceeds the configured character limit.")
        tokens = TOKEN_PATTERN.findall(text.lower())
        if not tokens:
            raise ValidationError("Embedding text must contain searchable tokens.")
        vector = [0.0 for _ in range(self.dimension)]
        seed = f"{self.provider}:{self.model}:{self.model_version}".encode()
        for token in tokens:
            digest = hashlib.sha256(seed + b":" + token.encode("utf-8")).digest()
            first_index = int.from_bytes(digest[:4], "big") % self.dimension
            second_index = int.from_bytes(digest[4:8], "big") % self.dimension
            first_sign = 1.0 if digest[8] % 2 == 0 else -1.0
            second_sign = 0.5 if digest[9] % 2 == 0 else -0.5
            vector[first_index] += first_sign
            vector[second_index] += second_sign
        return EmbeddingResult(
            item_id=request.item_id,
            vector=_normalize_vector(vector),
            token_count=len(tokens),
        )


def _normalize_vector(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude <= 0:
        raise IntegrityViolationError("Embedding provider returned a zero vector.")
    return [round(value / magnitude, 10) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise IntegrityViolationError("Embedding vector dimensions do not match.")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm <= 0 or right_norm <= 0:
        raise IntegrityViolationError("Embedding vector must not be zero.")
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)
