from __future__ import annotations

import time
from typing import Any

import jwt

from atlas_api.config import Settings

DEV_SECRET = "atlas-phase1-test-development-secret"  # noqa: S105 - deterministic test key


def make_settings() -> Settings:
    return Settings(
        atlas_env="test",
        auth_mode="development",
        auth_issuer="https://dev.atlas.local",
        auth_audience="atlas-api",
        auth_dev_secret=DEV_SECRET,
        database_url="postgresql+asyncpg://atlas:atlas_local_only@localhost:54329/atlas",
        object_store_root=".local-object-store-test",
        upload_signing_secret="atlas-phase2-test-upload-signing-secret",  # noqa: S106
        ops_internal_token="atlas-phase11-test-ops-internal-token",  # noqa: S106
    )


def token_for(subject: str, email: str, name: str | None = None) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "iss": "https://dev.atlas.local",
        "sub": subject,
        "aud": "atlas-api",
        "email": email,
        "name": name or email,
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, DEV_SECRET, algorithm="HS256")
