from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    atlas_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+asyncpg://atlas:atlas_local_only@localhost:54329/atlas"
    auth_mode: Literal["development", "oidc"] = "development"
    auth_issuer: str = "https://dev.atlas.local"
    auth_audience: str = "atlas-api"
    auth_jwks_url: str | None = None
    auth_dev_secret: str | None = Field(default=None, repr=False)
    cors_origins: str = "http://localhost:3000"
    object_store_root: str = ".local-object-store"
    upload_signing_secret: str | None = Field(default=None, repr=False)
    upload_intent_ttl_seconds: int = 900
    max_upload_bytes: int = 10 * 1024 * 1024
    parser_max_bytes: int = 1 * 1024 * 1024
    chunk_target_chars: int = 900
    chunk_overlap_chars: int = 120
    max_chunks_per_document: int = 500
    embedding_provider: Literal["deterministic-local"] = "deterministic-local"
    embedding_model: str = "atlas-local-hash-embedding"
    embedding_model_version: str = "2026-08-27"
    embedding_dimension: int = 32
    embedding_batch_size: int = 32
    embedding_max_text_chars: int = 4_000
    semantic_search_default_top_k: int = 5
    semantic_search_max_top_k: int = 20
    lexical_search_language: str = "english"
    hybrid_search_rrf_k: int = 60
    hybrid_search_candidate_multiplier: int = 4
    retrieval_config_version: str = "phase5-postgres-fts-rrf-v1"
    answer_provider: Literal["deterministic-local"] = "deterministic-local"
    answer_model: str = "atlas-local-grounded-generator"
    answer_model_version: str = "2026-08-28"
    answer_prompt_version: str = "phase6-grounded-answer-v1"
    answer_max_context_items: int = 5
    answer_max_context_chars: int = 2_400
    answer_max_output_chars: int = 1_200

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @model_validator(mode="after")
    def validate_auth_configuration(self) -> Settings:
        if self.auth_mode == "development":
            if self.atlas_env == "production":
                raise ValueError("development authentication is forbidden in production")
            if self.auth_dev_secret is None or len(self.auth_dev_secret) < 32:
                raise ValueError("AUTH_DEV_SECRET must contain at least 32 characters")
        elif not self.auth_jwks_url:
            raise ValueError("AUTH_JWKS_URL is required in oidc mode")
        if self.upload_signing_secret is None or len(self.upload_signing_secret) < 32:
            raise ValueError("UPLOAD_SIGNING_SECRET must contain at least 32 characters")
        if self.upload_intent_ttl_seconds < 60:
            raise ValueError("UPLOAD_INTENT_TTL_SECONDS must be at least 60")
        if self.max_upload_bytes < 1:
            raise ValueError("MAX_UPLOAD_BYTES must be positive")
        if self.parser_max_bytes < 1:
            raise ValueError("PARSER_MAX_BYTES must be positive")
        if self.chunk_target_chars < 200:
            raise ValueError("CHUNK_TARGET_CHARS must be at least 200")
        if self.chunk_overlap_chars < 0 or self.chunk_overlap_chars >= self.chunk_target_chars:
            raise ValueError("CHUNK_OVERLAP_CHARS must be non-negative and smaller than target")
        if self.max_chunks_per_document < 1:
            raise ValueError("MAX_CHUNKS_PER_DOCUMENT must be positive")
        if self.embedding_dimension < 8:
            raise ValueError("EMBEDDING_DIMENSION must be at least 8")
        if self.embedding_batch_size < 1:
            raise ValueError("EMBEDDING_BATCH_SIZE must be positive")
        if self.embedding_max_text_chars < 100:
            raise ValueError("EMBEDDING_MAX_TEXT_CHARS must be at least 100")
        if self.semantic_search_default_top_k < 1:
            raise ValueError("SEMANTIC_SEARCH_DEFAULT_TOP_K must be positive")
        if self.semantic_search_max_top_k < self.semantic_search_default_top_k:
            raise ValueError("SEMANTIC_SEARCH_MAX_TOP_K must be at least the default")
        if not self.lexical_search_language.strip():
            raise ValueError("LEXICAL_SEARCH_LANGUAGE must not be empty")
        if self.hybrid_search_rrf_k < 1:
            raise ValueError("HYBRID_SEARCH_RRF_K must be positive")
        if self.hybrid_search_candidate_multiplier < 1:
            raise ValueError("HYBRID_SEARCH_CANDIDATE_MULTIPLIER must be positive")
        if not self.retrieval_config_version.strip():
            raise ValueError("RETRIEVAL_CONFIG_VERSION must not be empty")
        if not self.answer_model.strip():
            raise ValueError("ANSWER_MODEL must not be empty")
        if not self.answer_model_version.strip():
            raise ValueError("ANSWER_MODEL_VERSION must not be empty")
        if not self.answer_prompt_version.strip():
            raise ValueError("ANSWER_PROMPT_VERSION must not be empty")
        if self.answer_max_context_items < 1:
            raise ValueError("ANSWER_MAX_CONTEXT_ITEMS must be positive")
        if self.answer_max_context_chars < 200:
            raise ValueError("ANSWER_MAX_CONTEXT_CHARS must be at least 200")
        if self.answer_max_output_chars < 200:
            raise ValueError("ANSWER_MAX_OUTPUT_CHARS must be at least 200")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
