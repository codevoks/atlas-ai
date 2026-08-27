from __future__ import annotations

import asyncio
import time
from typing import Any, Protocol

import httpx
import jwt
from jwt import PyJWK

from atlas_api.config import Settings
from atlas_api.domain.errors import DependencyUnavailableError, UnauthenticatedError
from atlas_api.domain.models import IdentityClaims


class IdentityVerifier(Protocol):
    async def verify(self, token: str) -> IdentityClaims: ...


def _claims_from_payload(payload: dict[str, Any], issuer: str) -> IdentityClaims:
    subject = payload.get("sub")
    email = payload.get("email")
    display_name = payload.get("name") or payload.get("preferred_username") or email
    if not isinstance(subject, str) or not subject:
        raise UnauthenticatedError()
    if not isinstance(email, str) or "@" not in email:
        raise UnauthenticatedError()
    if not isinstance(display_name, str) or not display_name.strip():
        raise UnauthenticatedError()
    return IdentityClaims(
        issuer=issuer,
        subject=subject,
        email=email.strip().lower(),
        display_name=display_name.strip(),
    )


class DevelopmentTokenVerifier:
    def __init__(self, settings: Settings) -> None:
        if settings.atlas_env == "production" or settings.auth_mode != "development":
            raise RuntimeError("Development token verifier cannot run outside development mode")
        if settings.auth_dev_secret is None:
            raise RuntimeError("Development secret is missing")
        self._secret = settings.auth_dev_secret
        self._issuer = settings.auth_issuer
        self._audience = settings.auth_audience

    async def verify(self, token: str) -> IdentityClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "iss", "sub", "aud", "email"]},
            )
        except jwt.PyJWTError as error:
            raise UnauthenticatedError() from error
        return _claims_from_payload(payload, self._issuer)


class OidcJwksVerifier:
    def __init__(self, settings: Settings, *, cache_seconds: int = 300) -> None:
        if settings.auth_jwks_url is None:
            raise RuntimeError("OIDC JWKS URL is missing")
        self._jwks_url = settings.auth_jwks_url
        self._issuer = settings.auth_issuer
        self._audience = settings.auth_audience
        self._cache_seconds = cache_seconds
        self._keys: dict[str, PyJWK] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def verify(self, token: str) -> IdentityClaims:
        try:
            header = jwt.get_unverified_header(token)
            key_id = header.get("kid")
            algorithm = header.get("alg")
            if not isinstance(key_id, str) or algorithm not in {"RS256", "EdDSA"}:
                raise UnauthenticatedError()
            key = await self._get_key(key_id)
            payload = jwt.decode(
                token,
                key.key,
                algorithms=[algorithm],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "iss", "sub", "aud", "email"]},
            )
        except UnauthenticatedError:
            raise
        except jwt.PyJWTError as error:
            raise UnauthenticatedError() from error
        return _claims_from_payload(payload, self._issuer)

    async def _get_key(self, key_id: str) -> PyJWK:
        if time.monotonic() >= self._expires_at or key_id not in self._keys:
            async with self._lock:
                if time.monotonic() >= self._expires_at or key_id not in self._keys:
                    await self._refresh()
        key = self._keys.get(key_id)
        if key is None:
            raise UnauthenticatedError()
        return key

    async def _refresh(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(self._jwks_url)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise DependencyUnavailableError("The identity provider is unavailable.") from error
        keys = payload.get("keys") if isinstance(payload, dict) else None
        if not isinstance(keys, list):
            raise DependencyUnavailableError("The identity provider returned invalid key data.")
        parsed: dict[str, PyJWK] = {}
        for raw_key in keys:
            if isinstance(raw_key, dict) and isinstance(raw_key.get("kid"), str):
                parsed[raw_key["kid"]] = PyJWK.from_dict(raw_key)
        if not parsed:
            raise DependencyUnavailableError("The identity provider returned no usable keys.")
        self._keys = parsed
        self._expires_at = time.monotonic() + self._cache_seconds


def create_identity_verifier(settings: Settings) -> IdentityVerifier:
    if settings.auth_mode == "development":
        return DevelopmentTokenVerifier(settings)
    return OidcJwksVerifier(settings)
