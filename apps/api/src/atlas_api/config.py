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
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
