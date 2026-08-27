from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol

from atlas_api.domain.models import (
    Actor,
    DocumentStatus,
    DocumentVersionStatus,
    IngestionJobState,
    MembershipContext,
    Role,
    SourceStatus,
    SourceType,
    UploadIntentStatus,
)


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    id: uuid.UUID
    name: str
    version: int
    role: Role


@dataclass(frozen=True, slots=True)
class MemberRecord:
    user_id: uuid.UUID
    email: str
    display_name: str
    role: Role
    version: int


@dataclass(frozen=True, slots=True)
class SourceRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    source_type: SourceType
    status: SourceStatus
    version: int


@dataclass(frozen=True, slots=True)
class UploadIntentRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    created_by_user_id: uuid.UUID
    object_key: str
    original_filename: str
    media_type: str
    byte_size: int
    digest_sha256: str
    status: UploadIntentStatus
    expires_at: datetime
    upload_url: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    source_id: uuid.UUID
    title: str
    status: DocumentStatus
    version: int
    latest_version_id: uuid.UUID | None
    latest_version_status: DocumentVersionStatus | None
    latest_job_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class DocumentVersionRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    object_key: str
    digest_sha256: str
    media_type: str
    byte_size: int
    status: DocumentVersionStatus
    active: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class IngestionJobRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    document_version_id: uuid.UUID
    state: IngestionJobState
    attempts: int
    max_attempts: int
    lease_owner: str | None
    lease_expires_at: datetime | None
    heartbeat_at: datetime | None
    progress: int
    error_class: str | None
    error_code: str | None
    error_message: str | None
    cancellation_requested: bool
    next_attempt_at: datetime
    version: int
    created_at: datetime


class WorkspaceStore(Protocol):
    async def membership_context(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, *, lock: bool = False
    ) -> MembershipContext | None: ...

    async def list_workspaces(self, user_id: uuid.UUID) -> list[WorkspaceRecord]: ...

    async def get_workspace(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkspaceRecord | None: ...

    async def create_workspace(
        self, actor: Actor, name: str, idempotency_key: str, request_id: str
    ) -> tuple[WorkspaceRecord, bool]: ...

    async def rename_workspace(
        self,
        workspace_id: uuid.UUID,
        name: str,
        expected_version: int,
        actor: Actor,
        actor_role: Role,
        request_id: str,
    ) -> WorkspaceRecord: ...

    async def list_members(self, workspace_id: uuid.UUID) -> list[MemberRecord]: ...

    async def add_member(
        self, workspace_id: uuid.UUID, email: str, role: Role, actor: Actor, request_id: str
    ) -> MemberRecord: ...

    async def update_member_role(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: Role,
        expected_version: int,
        actor: Actor,
        request_id: str,
    ) -> MemberRecord: ...

    async def remove_member(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, actor: Actor, request_id: str
    ) -> None: ...


class DocumentStore(Protocol):
    async def create_source(
        self, actor: Actor, workspace_id: uuid.UUID, name: str, request_id: str
    ) -> SourceRecord: ...

    async def list_sources(self, workspace_id: uuid.UUID) -> list[SourceRecord]: ...

    async def create_upload_intent(
        self,
        actor: Actor,
        workspace_id: uuid.UUID,
        original_filename: str,
        media_type: str,
        byte_size: int,
        digest_sha256: str,
        object_key: str,
        expires_at: datetime,
        request_id: str,
    ) -> UploadIntentRecord: ...

    async def get_upload_intent(self, intent_id: uuid.UUID) -> UploadIntentRecord | None: ...

    async def mark_upload_received(
        self, intent_id: uuid.UUID, byte_size: int, digest_sha256: str
    ) -> None: ...

    async def finalize_upload(
        self,
        actor: Actor,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        upload_intent_id: uuid.UUID,
        title: str,
        idempotency_key: str,
        request_id: str,
    ) -> tuple[DocumentRecord, DocumentVersionRecord, IngestionJobRecord, bool]: ...

    async def list_documents(
        self, actor: Actor, workspace_id: uuid.UUID
    ) -> list[DocumentRecord]: ...

    async def get_document(
        self, actor: Actor, workspace_id: uuid.UUID, document_id: uuid.UUID
    ) -> DocumentRecord | None: ...

    async def list_versions(
        self, actor: Actor, workspace_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[DocumentVersionRecord]: ...

    async def delete_document(
        self, actor: Actor, workspace_id: uuid.UUID, document_id: uuid.UUID, request_id: str
    ) -> None: ...

    async def get_job(
        self, actor: Actor, workspace_id: uuid.UUID, job_id: uuid.UUID
    ) -> IngestionJobRecord | None: ...

    async def cancel_job(
        self, actor: Actor, workspace_id: uuid.UUID, job_id: uuid.UUID, request_id: str
    ) -> IngestionJobRecord: ...

    async def retry_job(
        self, actor: Actor, workspace_id: uuid.UUID, job_id: uuid.UUID, request_id: str
    ) -> IngestionJobRecord: ...


class Transaction(Protocol):
    workspaces: WorkspaceStore
    documents: DocumentStore

    async def __aenter__(self) -> Transaction: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class TransactionFactory(Protocol):
    def __call__(self) -> Transaction: ...
