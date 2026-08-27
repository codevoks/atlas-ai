from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from atlas_api.application.ports import (
    DocumentRecord,
    DocumentVersionRecord,
    IngestionJobRecord,
    MemberRecord,
    SourceRecord,
    TransactionFactory,
    UploadIntentRecord,
    WorkspaceRecord,
)
from atlas_api.config import Settings
from atlas_api.domain.errors import (
    ForbiddenError,
    IntegrityViolationError,
    ResourceExhaustedError,
    ResourceNotFoundError,
    ValidationError,
)
from atlas_api.domain.models import Actor, Permission, Role
from atlas_api.domain.policy import can_manage_role, require_permission
from atlas_api.infrastructure.object_store import LocalObjectStore

ALLOWED_UPLOAD_MEDIA_TYPES = frozenset(
    {"text/plain", "text/markdown", "application/pdf", "application/octet-stream"}
)


class WorkspaceService:
    def __init__(self, transaction_factory: TransactionFactory) -> None:
        self._transactions = transaction_factory

    async def list_workspaces(self, actor: Actor) -> list[WorkspaceRecord]:
        async with self._transactions() as tx:
            return await tx.workspaces.list_workspaces(actor.user_id)

    async def get_workspace(self, actor: Actor, workspace_id: uuid.UUID) -> WorkspaceRecord:
        async with self._transactions() as tx:
            record = await tx.workspaces.get_workspace(workspace_id, actor.user_id)
            if record is None:
                raise ResourceNotFoundError()
            return record

    async def create_workspace(
        self, actor: Actor, name: str, idempotency_key: str, request_id: str
    ) -> tuple[WorkspaceRecord, bool]:
        async with self._transactions() as tx:
            return await tx.workspaces.create_workspace(actor, name, idempotency_key, request_id)

    async def rename_workspace(
        self,
        actor: Actor,
        workspace_id: uuid.UUID,
        name: str,
        expected_version: int,
        request_id: str,
    ) -> WorkspaceRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.WORKSPACE_UPDATE)
            return await tx.workspaces.rename_workspace(
                workspace_id, name, expected_version, actor, membership.role, request_id
            )

    async def list_members(self, actor: Actor, workspace_id: uuid.UUID) -> list[MemberRecord]:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.MEMBER_LIST)
            return await tx.workspaces.list_members(workspace_id)

    async def add_member(
        self,
        actor: Actor,
        workspace_id: uuid.UUID,
        email: str,
        role: Role,
        request_id: str,
    ) -> MemberRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.MEMBER_ADD)
            if not can_manage_role(membership.role, Role.VIEWER, role):
                raise ForbiddenError()
            return await tx.workspaces.add_member(workspace_id, email, role, actor, request_id)

    async def update_member_role(
        self,
        actor: Actor,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: Role,
        expected_version: int,
        request_id: str,
    ) -> MemberRecord:
        async with self._transactions() as tx:
            actor_membership = await tx.workspaces.membership_context(
                workspace_id, actor.user_id, lock=True
            )
            target_membership = await tx.workspaces.membership_context(
                workspace_id, user_id, lock=True
            )
            if actor_membership is None or target_membership is None:
                raise ResourceNotFoundError()
            require_permission(actor_membership, Permission.MEMBER_UPDATE)
            if not can_manage_role(actor_membership.role, target_membership.role, role):
                raise ForbiddenError()
            return await tx.workspaces.update_member_role(
                workspace_id, user_id, role, expected_version, actor, request_id
            )

    async def remove_member(
        self, actor: Actor, workspace_id: uuid.UUID, user_id: uuid.UUID, request_id: str
    ) -> None:
        async with self._transactions() as tx:
            actor_membership = await tx.workspaces.membership_context(
                workspace_id, actor.user_id, lock=True
            )
            target_membership = await tx.workspaces.membership_context(
                workspace_id, user_id, lock=True
            )
            if actor_membership is None or target_membership is None:
                raise ResourceNotFoundError()
            require_permission(actor_membership, Permission.MEMBER_REMOVE)
            if not can_manage_role(actor_membership.role, target_membership.role, None):
                raise ForbiddenError()
            await tx.workspaces.remove_member(workspace_id, user_id, actor, request_id)


class DocumentService:
    def __init__(
        self,
        transaction_factory: TransactionFactory,
        object_store: LocalObjectStore,
        settings: Settings,
    ) -> None:
        self._transactions = transaction_factory
        self._object_store = object_store
        self._settings = settings

    async def create_source(
        self, actor: Actor, workspace_id: uuid.UUID, name: str, request_id: str
    ) -> SourceRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.SOURCE_CREATE)
            return await tx.documents.create_source(
                actor, workspace_id, self._clean_name(name), request_id
            )

    async def list_sources(self, actor: Actor, workspace_id: uuid.UUID) -> list[SourceRecord]:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.SOURCE_READ)
            return await tx.documents.list_sources(workspace_id)

    async def create_upload_intent(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        original_filename: str,
        media_type: str,
        byte_size: int,
        digest_sha256: str,
        base_url: str,
        request_id: str,
    ) -> UploadIntentRecord:
        filename = self._clean_filename(original_filename)
        clean_media_type = media_type.strip().lower()
        clean_digest = digest_sha256.strip().lower()
        if clean_media_type not in ALLOWED_UPLOAD_MEDIA_TYPES:
            raise ValidationError("The upload media type is not supported.")
        if byte_size <= 0:
            raise ValidationError("Upload byte size must be positive.")
        if byte_size > self._settings.max_upload_bytes:
            raise ResourceExhaustedError("The upload exceeds the workspace upload limit.")
        if len(clean_digest) != 64 or any(char not in "0123456789abcdef" for char in clean_digest):
            raise ValidationError("digest_sha256 must be a lowercase hexadecimal SHA-256 digest.")

        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_CREATE)
            intent_id = uuid.uuid4()
            expires_at = datetime.now(UTC) + timedelta(
                seconds=self._settings.upload_intent_ttl_seconds
            )
            object_key = self._object_store.object_key(workspace_id, intent_id, filename)
            record = await tx.documents.create_upload_intent(
                actor,
                workspace_id,
                filename,
                clean_media_type,
                byte_size,
                clean_digest,
                object_key,
                expires_at,
                request_id,
            )
        upload_url = self._object_store.signed_upload_url(
            base_url=base_url,
            upload_intent_id=record.id,
            object_key=record.object_key,
            expires_at=record.expires_at,
        )
        return UploadIntentRecord(
            id=record.id,
            workspace_id=record.workspace_id,
            created_by_user_id=record.created_by_user_id,
            object_key=record.object_key,
            original_filename=record.original_filename,
            media_type=record.media_type,
            byte_size=record.byte_size,
            digest_sha256=record.digest_sha256,
            status=record.status,
            expires_at=record.expires_at,
            upload_url=upload_url,
        )

    async def receive_upload_content(
        self,
        *,
        upload_intent_id: uuid.UUID,
        token: str,
        body: bytes,
        media_type: str,
    ) -> UploadIntentRecord:
        async with self._transactions() as tx:
            intent = await tx.documents.get_upload_intent(upload_intent_id)
            if intent is None:
                raise ResourceNotFoundError()
            now = datetime.now(UTC)
            if intent.expires_at < now:
                raise ValidationError("The upload intent has expired.")
            if intent.byte_size != len(body):
                raise IntegrityViolationError(
                    "The uploaded object byte size does not match the intent."
                )
            if intent.media_type != media_type.strip().lower():
                raise ValidationError("The upload media type does not match the intent.")
            self._object_store.verify_upload_token(
                upload_intent_id=intent.id,
                object_key=intent.object_key,
                token=token,
                now=now,
            )
            metadata = await self._object_store.put_bytes(
                object_key=intent.object_key,
                body=body,
                media_type=intent.media_type,
                expected_digest=intent.digest_sha256,
            )
            if metadata.byte_size != intent.byte_size:
                raise IntegrityViolationError(
                    "The uploaded object byte size does not match the intent."
                )
            await tx.documents.mark_upload_received(
                intent.id, metadata.byte_size, metadata.digest_sha256
            )
            updated = await tx.documents.get_upload_intent(upload_intent_id)
            if updated is None:
                raise ResourceNotFoundError()
            return updated

    async def finalize_upload(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        upload_intent_id: uuid.UUID,
        title: str,
        idempotency_key: str,
        request_id: str,
    ) -> tuple[DocumentRecord, DocumentVersionRecord, IngestionJobRecord, bool]:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_CREATE)
            intent = await tx.documents.get_upload_intent(upload_intent_id)
            if intent is None or intent.workspace_id != workspace_id:
                raise ResourceNotFoundError()
            metadata = await self._object_store.head(intent.object_key)
            if (
                metadata.byte_size != intent.byte_size
                or metadata.digest_sha256 != intent.digest_sha256
            ):
                raise IntegrityViolationError(
                    "The stored object does not match the finalized intent."
                )
            return await tx.documents.finalize_upload(
                actor,
                workspace_id,
                source_id,
                upload_intent_id,
                self._clean_title(title),
                idempotency_key,
                request_id,
            )

    async def list_documents(self, actor: Actor, workspace_id: uuid.UUID) -> list[DocumentRecord]:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            return await tx.documents.list_documents(actor, workspace_id)

    async def get_document(
        self, actor: Actor, workspace_id: uuid.UUID, document_id: uuid.UUID
    ) -> DocumentRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            record = await tx.documents.get_document(actor, workspace_id, document_id)
            if record is None:
                raise ResourceNotFoundError()
            return record

    async def list_versions(
        self, actor: Actor, workspace_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[DocumentVersionRecord]:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            return await tx.documents.list_versions(actor, workspace_id, document_id)

    async def delete_document(
        self, actor: Actor, workspace_id: uuid.UUID, document_id: uuid.UUID, request_id: str
    ) -> None:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_DELETE)
            await tx.documents.delete_document(actor, workspace_id, document_id, request_id)

    async def get_job(
        self, actor: Actor, workspace_id: uuid.UUID, job_id: uuid.UUID
    ) -> IngestionJobRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.INGESTION_JOB_READ)
            record = await tx.documents.get_job(actor, workspace_id, job_id)
            if record is None:
                raise ResourceNotFoundError()
            return record

    async def cancel_job(
        self, actor: Actor, workspace_id: uuid.UUID, job_id: uuid.UUID, request_id: str
    ) -> IngestionJobRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.INGESTION_JOB_MANAGE)
            return await tx.documents.cancel_job(actor, workspace_id, job_id, request_id)

    async def retry_job(
        self, actor: Actor, workspace_id: uuid.UUID, job_id: uuid.UUID, request_id: str
    ) -> IngestionJobRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.INGESTION_JOB_MANAGE)
            return await tx.documents.retry_job(actor, workspace_id, job_id, request_id)

    @staticmethod
    def _clean_name(value: str) -> str:
        normalized = " ".join(value.split())
        if not 2 <= len(normalized) <= 160:
            raise ValidationError("The source name must contain between 2 and 160 characters.")
        return normalized

    @staticmethod
    def _clean_title(value: str) -> str:
        normalized = " ".join(value.split())
        if not 1 <= len(normalized) <= 255:
            raise ValidationError("The document title must contain between 1 and 255 characters.")
        return normalized

    @staticmethod
    def _clean_filename(value: str) -> str:
        filename = Path(value).name.strip()
        if not filename or filename in {".", ".."}:
            raise ValidationError("The upload filename is invalid.")
        if len(filename) > 255:
            raise ValidationError("The upload filename is too long.")
        return filename
