from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from atlas_api.config import Settings
from atlas_api.domain.errors import UnauthenticatedError
from atlas_api.security.authentication import DevelopmentTokenVerifier
from tests.support import DEV_SECRET, token_for


@pytest.mark.asyncio
async def test_development_token_verifier_accepts_expected_claims() -> None:
    settings = Settings(
        atlas_env="test",
        auth_mode="development",
        auth_dev_secret=DEV_SECRET,
        auth_issuer="https://dev.atlas.local",
        auth_audience="atlas-api",
    )
    verifier = DevelopmentTokenVerifier(settings)

    claims = await verifier.verify(token_for("alice", "ALICE@example.com", "Alice"))

    assert claims.subject == "alice"
    assert claims.email == "alice@example.com"
    assert claims.display_name == "Alice"


@pytest.mark.asyncio
async def test_development_token_verifier_rejects_wrong_audience() -> None:
    settings = Settings(atlas_env="test", auth_mode="development", auth_dev_secret=DEV_SECRET)
    verifier = DevelopmentTokenVerifier(settings)

    bad_token = token_for("alice", "alice@example.com").replace(".", "-", 1)

    with pytest.raises(UnauthenticatedError):
        await verifier.verify(bad_token)


def test_development_auth_is_forbidden_in_production() -> None:
    with pytest.raises(PydanticValidationError):
        Settings(
            atlas_env="production",
            auth_mode="development",
            auth_dev_secret=DEV_SECRET,
        )
