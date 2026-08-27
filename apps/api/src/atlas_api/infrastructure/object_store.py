from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from atlas_api.config import Settings
from atlas_api.domain.errors import (
    ConflictError,
    IntegrityViolationError,
    ResourceNotFoundError,
    ValidationError,
)


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    object_key: str
    byte_size: int
    digest_sha256: str
    media_type: str


class LocalObjectStore:
    def __init__(self, settings: Settings) -> None:
        configured_root = Path(settings.object_store_root)
        if configured_root.is_absolute():
            self._root = configured_root.resolve()
        else:
            repository_root = Path(__file__).resolve().parents[5]
            self._root = (repository_root / configured_root).resolve()
        self._secret = (settings.upload_signing_secret or "").encode("utf-8")

    def object_key(
        self, workspace_id: uuid.UUID, upload_intent_id: uuid.UUID, filename: str
    ) -> str:
        safe_suffix = Path(filename).name.replace("/", "_").replace("\\", "_") or "upload.bin"
        return f"workspaces/{workspace_id}/uploads/{upload_intent_id}/{safe_suffix}"

    def signed_upload_url(
        self,
        *,
        base_url: str,
        upload_intent_id: uuid.UUID,
        object_key: str,
        expires_at: datetime,
    ) -> str:
        expires_epoch = int(expires_at.timestamp())
        payload = f"{upload_intent_id}:{object_key}:{expires_epoch}"
        signature = hmac.new(self._secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        token = base64.urlsafe_b64encode(f"{expires_epoch}:{signature}".encode()).decode("ascii")
        return f"{base_url}/v1/uploads/{upload_intent_id}/content?token={quote(token)}"

    def verify_upload_token(
        self,
        *,
        upload_intent_id: uuid.UUID,
        object_key: str,
        token: str,
        now: datetime,
    ) -> None:
        try:
            decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
            expires_raw, signature = decoded.split(":", 1)
            expires_epoch = int(expires_raw)
        except (ValueError, UnicodeDecodeError) as error:
            raise ValidationError("The upload token is invalid.") from error
        if datetime.fromtimestamp(expires_epoch, tz=UTC) < now:
            raise ValidationError("The upload token has expired.")
        payload = f"{upload_intent_id}:{object_key}:{expires_epoch}"
        expected = hmac.new(self._secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValidationError("The upload token is invalid.")

    async def put_bytes(
        self, *, object_key: str, body: bytes, media_type: str, expected_digest: str
    ) -> ObjectMetadata:
        self._assert_safe_key(object_key)
        digest = hashlib.sha256(body).hexdigest()
        if digest != expected_digest:
            raise IntegrityViolationError("The uploaded object digest does not match the intent.")
        path = self._path_for(object_key)
        if path.exists():
            existing = path.read_bytes()
            if hashlib.sha256(existing).hexdigest() != digest:
                raise ConflictError("The object key already contains different bytes.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return ObjectMetadata(
            object_key=object_key,
            byte_size=len(body),
            digest_sha256=digest,
            media_type=media_type,
        )

    async def put_derived_bytes(
        self, *, object_key: str, body: bytes, media_type: str
    ) -> ObjectMetadata:
        self._assert_safe_key(object_key)
        digest = hashlib.sha256(body).hexdigest()
        path = self._path_for(object_key)
        if path.exists():
            existing = path.read_bytes()
            if hashlib.sha256(existing).hexdigest() != digest:
                raise ConflictError("The object key already contains different bytes.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return ObjectMetadata(
            object_key=object_key,
            byte_size=len(body),
            digest_sha256=digest,
            media_type=media_type,
        )

    async def get_bytes(self, object_key: str) -> bytes:
        self._assert_safe_key(object_key)
        path = self._path_for(object_key)
        if not path.exists():
            raise ResourceNotFoundError("The uploaded object was not found.")
        return path.read_bytes()

    async def head(self, object_key: str) -> ObjectMetadata:
        self._assert_safe_key(object_key)
        path = self._path_for(object_key)
        if not path.exists():
            raise ResourceNotFoundError("The uploaded object was not found.")
        data = path.read_bytes()
        return ObjectMetadata(
            object_key=object_key,
            byte_size=len(data),
            digest_sha256=hashlib.sha256(data).hexdigest(),
            media_type="application/octet-stream",
        )

    async def delete(self, object_key: str) -> None:
        self._assert_safe_key(object_key)
        path = self._path_for(object_key)
        if path.exists():
            path.unlink()

    def _path_for(self, object_key: str) -> Path:
        path = (self._root / object_key).resolve()
        if self._root not in path.parents:
            raise ValidationError("The object key is invalid.")
        return path

    @staticmethod
    def _assert_safe_key(object_key: str) -> None:
        if object_key.startswith("/") or ".." in Path(object_key).parts:
            raise ValidationError("The object key is invalid.")
