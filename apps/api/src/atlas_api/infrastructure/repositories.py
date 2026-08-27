from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import TracebackType

from sqlalchemy import Select, and_, delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from atlas_api.application.embeddings import cosine_similarity
from atlas_api.application.ports import (
    AnswerEvidenceDraft,
    AnswerEvidenceRecord,
    AnswerRunRecord,
    ChunkDraftRecord,
    ChunkEmbeddingDraftRecord,
    ChunkEmbeddingWriteRecord,
    ChunkRecord,
    CitationDraft,
    DocumentRecord,
    DocumentStore,
    DocumentVersionRecord,
    EmbeddingCoverageRecord,
    EmbeddingSetRecord,
    IngestionJobRecord,
    MemberRecord,
    MissingEmbeddingChunkRecord,
    SearchCandidate,
    SearchFilter,
    SourceRecord,
    Transaction,
    UploadIntentRecord,
    ValidatedCitationRecord,
    WorkspaceRecord,
    WorkspaceStore,
)
from atlas_api.domain.errors import ConflictError, ResourceNotFoundError
from atlas_api.domain.models import (
    Actor,
    AnswerRunStatus,
    ChunkEmbeddingStatus,
    CitationValidationStatus,
    DocumentStatus,
    DocumentVersionStatus,
    EmbeddingSetStatus,
    IdentityClaims,
    IngestionJobState,
    MembershipContext,
    MembershipStatus,
    RetryClass,
    Role,
    SourceStatus,
    SourceType,
    UploadIntentStatus,
)
from atlas_api.infrastructure.models import (
    AnswerEvidenceModel,
    AnswerRunModel,
    AuditEventModel,
    ChunkEmbeddingModel,
    ChunkModel,
    CitationModel,
    DocumentModel,
    DocumentVersionModel,
    EmbeddingSetModel,
    IdempotencyRecordModel,
    IngestionJobModel,
    JobEventModel,
    MembershipModel,
    SourceModel,
    UploadIntentModel,
    UserModel,
    WorkspaceModel,
)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _advisory_lock_id(value: str) -> int:
    unsigned = int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:8], "big")
    return unsigned if unsigned < 2**63 else unsigned - 2**64


class IdentityRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def resolve(self, claims: IdentityClaims) -> Actor:
        normalized_email = claims.email.strip().lower()
        async with self._sessions() as session, session.begin():
            existing = await session.scalar(
                select(UserModel).where(
                    UserModel.issuer == claims.issuer,
                    UserModel.subject == claims.subject,
                )
            )
            if existing is None:
                existing = UserModel(
                    issuer=claims.issuer,
                    subject=claims.subject,
                    email=normalized_email,
                    display_name=claims.display_name.strip(),
                )
                session.add(existing)
                try:
                    await session.flush()
                except IntegrityError as error:
                    raise ConflictError(
                        "The identity email is already associated with another subject."
                    ) from error
            else:
                existing.email = normalized_email
                existing.display_name = claims.display_name.strip()
            await session.flush()
            return Actor(
                user_id=existing.id,
                issuer=existing.issuer,
                subject=existing.subject,
                email=existing.email,
                display_name=existing.display_name,
            )


class SqlAlchemyWorkspaceStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def membership_context(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, *, lock: bool = False
    ) -> MembershipContext | None:
        if lock:
            await self._session.execute(
                select(WorkspaceModel.id).where(WorkspaceModel.id == workspace_id).with_for_update()
            )
        statement: Select[tuple[MembershipModel]] = select(MembershipModel).where(
            MembershipModel.workspace_id == workspace_id,
            MembershipModel.user_id == user_id,
        )
        membership = await self._session.scalar(statement)
        if membership is None:
            return None
        return MembershipContext(
            workspace_id=membership.workspace_id,
            user_id=membership.user_id,
            role=Role(membership.role),
            status=MembershipStatus(membership.status),
        )

    async def list_workspaces(self, user_id: uuid.UUID) -> list[WorkspaceRecord]:
        rows = (
            await self._session.execute(
                select(WorkspaceModel, MembershipModel.role)
                .join(
                    MembershipModel,
                    (MembershipModel.workspace_id == WorkspaceModel.id)
                    & (MembershipModel.user_id == user_id),
                )
                .where(MembershipModel.status == MembershipStatus.ACTIVE.value)
                .order_by(WorkspaceModel.created_at.asc(), WorkspaceModel.id.asc())
            )
        ).all()
        return [
            WorkspaceRecord(
                id=workspace.id, name=workspace.name, version=workspace.version, role=Role(role)
            )
            for workspace, role in rows
        ]

    async def get_workspace(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkspaceRecord | None:
        row = (
            await self._session.execute(
                select(WorkspaceModel, MembershipModel.role)
                .join(
                    MembershipModel,
                    (MembershipModel.workspace_id == WorkspaceModel.id)
                    & (MembershipModel.user_id == user_id),
                )
                .where(
                    WorkspaceModel.id == workspace_id,
                    MembershipModel.status == MembershipStatus.ACTIVE.value,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        workspace, role = row
        return WorkspaceRecord(
            id=workspace.id, name=workspace.name, version=workspace.version, role=Role(role)
        )

    async def create_workspace(
        self, actor: Actor, name: str, idempotency_key: str, request_id: str
    ) -> tuple[WorkspaceRecord, bool]:
        operation = "workspace:create"
        key_hash = _sha256(idempotency_key)
        request_hash = _sha256(json.dumps({"name": name}, sort_keys=True))
        lock_id = _advisory_lock_id(f"{actor.user_id}:{operation}:{key_hash}")
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id}
        )

        prior = await self._session.scalar(
            select(IdempotencyRecordModel).where(
                IdempotencyRecordModel.actor_user_id == actor.user_id,
                IdempotencyRecordModel.operation == operation,
                IdempotencyRecordModel.key_hash == key_hash,
            )
        )
        if prior is not None:
            if prior.request_hash != request_hash:
                raise ConflictError("The idempotency key was already used for a different request.")
            body = prior.response_body
            return (
                WorkspaceRecord(
                    id=uuid.UUID(body["id"]),
                    name=str(body["name"]),
                    version=int(body["version"]),
                    role=Role(str(body["role"])),
                ),
                True,
            )

        workspace = WorkspaceModel(name=name)
        self._session.add(workspace)
        await self._session.flush()
        membership = MembershipModel(
            workspace_id=workspace.id,
            user_id=actor.user_id,
            role=Role.OWNER.value,
            status=MembershipStatus.ACTIVE.value,
        )
        self._session.add(membership)
        await self._audit(
            workspace.id,
            actor,
            "workspace.created",
            "workspace",
            workspace.id,
            request_id,
            {"name": name},
        )
        record = WorkspaceRecord(
            id=workspace.id, name=workspace.name, version=workspace.version, role=Role.OWNER
        )
        self._session.add(
            IdempotencyRecordModel(
                actor_user_id=actor.user_id,
                operation=operation,
                key_hash=key_hash,
                request_hash=request_hash,
                response_status=201,
                response_body={
                    "id": str(record.id),
                    "name": record.name,
                    "version": record.version,
                    "role": record.role.value,
                },
            )
        )
        return record, False

    async def rename_workspace(
        self,
        workspace_id: uuid.UUID,
        name: str,
        expected_version: int,
        actor: Actor,
        actor_role: Role,
        request_id: str,
    ) -> WorkspaceRecord:
        row = (
            await self._session.execute(
                update(WorkspaceModel)
                .where(
                    WorkspaceModel.id == workspace_id, WorkspaceModel.version == expected_version
                )
                .values(name=name, version=WorkspaceModel.version + 1)
                .returning(WorkspaceModel.id, WorkspaceModel.name, WorkspaceModel.version)
            )
        ).one_or_none()
        if row is None:
            exists = await self._session.scalar(
                select(WorkspaceModel.id).where(WorkspaceModel.id == workspace_id)
            )
            if exists is None:
                raise ResourceNotFoundError()
            raise ConflictError("The workspace changed; refresh and retry.")
        await self._audit(
            workspace_id,
            actor,
            "workspace.renamed",
            "workspace",
            workspace_id,
            request_id,
            {"name": name},
        )
        return WorkspaceRecord(id=row.id, name=row.name, version=row.version, role=actor_role)

    async def list_members(self, workspace_id: uuid.UUID) -> list[MemberRecord]:
        rows = (
            await self._session.execute(
                select(MembershipModel, UserModel)
                .join(UserModel, UserModel.id == MembershipModel.user_id)
                .where(
                    MembershipModel.workspace_id == workspace_id,
                    MembershipModel.status == MembershipStatus.ACTIVE.value,
                )
                .order_by(UserModel.email.asc())
            )
        ).all()
        return [self._member_record(membership, user) for membership, user in rows]

    async def add_member(
        self, workspace_id: uuid.UUID, email: str, role: Role, actor: Actor, request_id: str
    ) -> MemberRecord:
        user = await self._session.scalar(
            select(UserModel).where(
                UserModel.issuer == actor.issuer,
                func.lower(UserModel.email) == email.strip().lower(),
            )
        )
        if user is None:
            raise ResourceNotFoundError(
                "The user must sign in once before membership can be added."
            )
        existing = await self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.workspace_id == workspace_id,
                MembershipModel.user_id == user.id,
            )
        )
        if existing is not None:
            raise ConflictError("The user is already a workspace member.")
        membership = MembershipModel(
            workspace_id=workspace_id,
            user_id=user.id,
            role=role.value,
            status=MembershipStatus.ACTIVE.value,
        )
        self._session.add(membership)
        await self._session.flush()
        await self._audit(
            workspace_id,
            actor,
            "membership.added",
            "user",
            user.id,
            request_id,
            {"role": role.value},
        )
        return self._member_record(membership, user)

    async def update_member_role(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: Role,
        expected_version: int,
        actor: Actor,
        request_id: str,
    ) -> MemberRecord:
        membership = await self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.workspace_id == workspace_id,
                MembershipModel.user_id == user_id,
            )
        )
        if membership is None:
            raise ResourceNotFoundError()
        if membership.version != expected_version:
            raise ConflictError("The membership changed; refresh and retry.")
        if membership.role == Role.OWNER.value and role is not Role.OWNER:
            await self._require_another_owner(workspace_id, user_id)
        membership.role = role.value
        membership.version += 1
        user = await self._session.get(UserModel, user_id)
        if user is None:
            raise ResourceNotFoundError()
        await self._audit(
            workspace_id,
            actor,
            "membership.role_changed",
            "user",
            user_id,
            request_id,
            {"role": role.value},
        )
        return self._member_record(membership, user)

    async def remove_member(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, actor: Actor, request_id: str
    ) -> None:
        membership = await self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.workspace_id == workspace_id,
                MembershipModel.user_id == user_id,
            )
        )
        if membership is None:
            raise ResourceNotFoundError()
        if membership.role == Role.OWNER.value:
            await self._require_another_owner(workspace_id, user_id)
        await self._session.delete(membership)
        await self._audit(
            workspace_id, actor, "membership.removed", "user", user_id, request_id, {}
        )

    async def _require_another_owner(
        self, workspace_id: uuid.UUID, excluded_user_id: uuid.UUID
    ) -> None:
        other_owner = await self._session.scalar(
            select(MembershipModel.id).where(
                MembershipModel.workspace_id == workspace_id,
                MembershipModel.user_id != excluded_user_id,
                MembershipModel.role == Role.OWNER.value,
                MembershipModel.status == MembershipStatus.ACTIVE.value,
            )
        )
        if other_owner is None:
            raise ConflictError("A workspace must retain at least one active owner.")

    async def _audit(
        self,
        workspace_id: uuid.UUID,
        actor: Actor,
        action: str,
        target_type: str,
        target_id: uuid.UUID,
        request_id: str,
        safe_metadata: dict[str, str],
    ) -> None:
        self._session.add(
            AuditEventModel(
                workspace_id=workspace_id,
                actor_user_id=actor.user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                request_id=request_id,
                safe_metadata=safe_metadata,
            )
        )

    @staticmethod
    def _member_record(membership: MembershipModel, user: UserModel) -> MemberRecord:
        return MemberRecord(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=Role(membership.role),
            version=membership.version,
        )


class SqlAlchemyDocumentStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_source(
        self, actor: Actor, workspace_id: uuid.UUID, name: str, request_id: str
    ) -> SourceRecord:
        source = SourceModel(
            workspace_id=workspace_id,
            name=name,
            source_type=SourceType.UPLOAD.value,
            status=SourceStatus.ACTIVE.value,
            safe_metadata={},
        )
        self._session.add(source)
        await self._session.flush()
        await self._audit(
            workspace_id, actor, "source.created", "source", source.id, request_id, {"name": name}
        )
        return self._source_record(source)

    async def list_sources(self, workspace_id: uuid.UUID) -> list[SourceRecord]:
        rows = (
            await self._session.scalars(
                select(SourceModel)
                .where(
                    SourceModel.workspace_id == workspace_id,
                    SourceModel.status == SourceStatus.ACTIVE.value,
                )
                .order_by(SourceModel.created_at.asc(), SourceModel.id.asc())
            )
        ).all()
        return [self._source_record(row) for row in rows]

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
    ) -> UploadIntentRecord:
        intent = UploadIntentModel(
            workspace_id=workspace_id,
            created_by_user_id=actor.user_id,
            object_key=object_key,
            original_filename=original_filename,
            media_type=media_type,
            byte_size=byte_size,
            digest_sha256=digest_sha256,
            status=UploadIntentStatus.PENDING.value,
            expires_at=expires_at,
        )
        self._session.add(intent)
        await self._session.flush()
        await self._audit(
            workspace_id,
            actor,
            "upload_intent.created",
            "upload_intent",
            intent.id,
            request_id,
            {"media_type": media_type},
        )
        return self._upload_intent_record(intent)

    async def get_upload_intent(self, intent_id: uuid.UUID) -> UploadIntentRecord | None:
        intent = await self._session.get(UploadIntentModel, intent_id)
        return None if intent is None else self._upload_intent_record(intent)

    async def mark_upload_received(
        self, intent_id: uuid.UUID, byte_size: int, digest_sha256: str
    ) -> None:
        intent = await self._session.get(UploadIntentModel, intent_id, with_for_update=True)
        if intent is None:
            raise ResourceNotFoundError()
        if intent.byte_size != byte_size or intent.digest_sha256 != digest_sha256:
            raise ConflictError("The upload receipt does not match the upload intent.")
        if intent.status == UploadIntentStatus.FINALIZED.value:
            raise ConflictError("The upload intent has already been finalized.")
        intent.status = UploadIntentStatus.UPLOADED.value

    async def finalize_upload(
        self,
        actor: Actor,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        upload_intent_id: uuid.UUID,
        title: str,
        idempotency_key: str,
        request_id: str,
    ) -> tuple[DocumentRecord, DocumentVersionRecord, IngestionJobRecord, bool]:
        operation = "upload:finalize"
        request_body = {
            "workspace_id": str(workspace_id),
            "source_id": str(source_id),
            "upload_intent_id": str(upload_intent_id),
            "title": title,
        }
        key_hash = _sha256(idempotency_key)
        request_hash = _sha256(json.dumps(request_body, sort_keys=True))
        lock_id = _advisory_lock_id(f"{actor.user_id}:{operation}:{key_hash}")
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id}
        )
        prior = await self._session.scalar(
            select(IdempotencyRecordModel).where(
                IdempotencyRecordModel.actor_user_id == actor.user_id,
                IdempotencyRecordModel.operation == operation,
                IdempotencyRecordModel.key_hash == key_hash,
            )
        )
        if prior is not None:
            if prior.request_hash != request_hash:
                raise ConflictError("The idempotency key was already used for a different request.")
            document_record, version_record, job_record = await self._records_from_response(
                prior.response_body
            )
            return document_record, version_record, job_record, True

        source = await self._session.scalar(
            select(SourceModel).where(
                SourceModel.id == source_id,
                SourceModel.workspace_id == workspace_id,
                SourceModel.status == SourceStatus.ACTIVE.value,
            )
        )
        if source is None:
            raise ResourceNotFoundError()

        intent = await self._session.get(UploadIntentModel, upload_intent_id, with_for_update=True)
        if intent is None or intent.workspace_id != workspace_id:
            raise ResourceNotFoundError()
        if intent.created_by_user_id != actor.user_id:
            raise ConflictError("Only the upload creator can finalize this upload intent.")
        if intent.status == UploadIntentStatus.FINALIZED.value:
            raise ConflictError("The upload intent has already been finalized.")
        if intent.status != UploadIntentStatus.UPLOADED.value:
            raise ConflictError("The upload intent must be uploaded before finalization.")
        if intent.expires_at < datetime.now(UTC):
            intent.status = UploadIntentStatus.EXPIRED.value
            raise ConflictError("The upload intent has expired.")

        document_model = DocumentModel(
            workspace_id=workspace_id,
            source_id=source_id,
            title=title,
            status=DocumentStatus.ACTIVE.value,
            created_by_user_id=actor.user_id,
        )
        self._session.add(document_model)
        await self._session.flush()

        document_version = DocumentVersionModel(
            workspace_id=workspace_id,
            document_id=document_model.id,
            version_number=1,
            object_key=intent.object_key,
            digest_sha256=intent.digest_sha256,
            media_type=intent.media_type,
            byte_size=intent.byte_size,
            status=DocumentVersionStatus.INGESTION_PENDING.value,
            active=False,
            parser_config={
                "phase": 3,
                "operation": "parse_normalize_chunk",
                "supported_media_types": ["text/plain", "text/markdown", "application/markdown"],
            },
            created_by_user_id=actor.user_id,
        )
        self._session.add(document_version)
        await self._session.flush()

        job = IngestionJobModel(
            workspace_id=workspace_id,
            document_version_id=document_version.id,
            job_type="ingest_document",
            state=IngestionJobState.PENDING.value,
            attempts=0,
            max_attempts=3,
            progress=0,
            cancellation_requested=False,
            idempotency_key=f"ingest:{document_version.id}",
            config={"phase": 3, "operation": "verify_parse_normalize_chunk_publish"},
        )
        self._session.add(job)
        intent.status = UploadIntentStatus.FINALIZED.value
        intent.finalized_document_version_id = document_version.id
        await self._session.flush()
        await self._job_event(
            workspace_id, job.id, None, IngestionJobState.PENDING, "upload_finalized", {}
        )
        await self._audit(
            workspace_id,
            actor,
            "document_version.created",
            "document_version",
            document_version.id,
            request_id,
            {"document_id": str(document_model.id)},
        )

        created_document_record = await self.get_document(actor, workspace_id, document_model.id)
        if created_document_record is None:
            raise ResourceNotFoundError()
        version_record = self._version_record(document_version)
        job_record = self._job_record(job)
        response_body = self._response_body(created_document_record, version_record, job_record)
        self._session.add(
            IdempotencyRecordModel(
                actor_user_id=actor.user_id,
                operation=operation,
                key_hash=key_hash,
                request_hash=request_hash,
                response_status=201,
                response_body=response_body,
            )
        )
        return created_document_record, version_record, job_record, False

    async def list_documents(self, actor: Actor, workspace_id: uuid.UUID) -> list[DocumentRecord]:
        documents = (
            await self._session.scalars(
                select(DocumentModel)
                .where(
                    DocumentModel.workspace_id == workspace_id,
                    DocumentModel.status == DocumentStatus.ACTIVE.value,
                )
                .order_by(DocumentModel.created_at.desc(), DocumentModel.id.asc())
            )
        ).all()
        return [await self._document_record(document) for document in documents]

    async def get_document(
        self, actor: Actor, workspace_id: uuid.UUID, document_id: uuid.UUID
    ) -> DocumentRecord | None:
        document = await self._session.scalar(
            select(DocumentModel).where(
                DocumentModel.id == document_id,
                DocumentModel.workspace_id == workspace_id,
                DocumentModel.status == DocumentStatus.ACTIVE.value,
            )
        )
        return None if document is None else await self._document_record(document)

    async def list_versions(
        self, actor: Actor, workspace_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[DocumentVersionRecord]:
        exists = await self._session.scalar(
            select(DocumentModel.id).where(
                DocumentModel.id == document_id,
                DocumentModel.workspace_id == workspace_id,
                DocumentModel.status == DocumentStatus.ACTIVE.value,
            )
        )
        if exists is None:
            raise ResourceNotFoundError()
        versions = (
            await self._session.scalars(
                select(DocumentVersionModel)
                .where(
                    DocumentVersionModel.workspace_id == workspace_id,
                    DocumentVersionModel.document_id == document_id,
                )
                .order_by(DocumentVersionModel.version_number.desc())
            )
        ).all()
        return [self._version_record(row) for row in versions]

    async def list_chunks(
        self,
        actor: Actor,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> list[ChunkRecord]:
        exists = await self._session.scalar(
            select(DocumentVersionModel.id)
            .join(DocumentModel, DocumentModel.id == DocumentVersionModel.document_id)
            .where(
                DocumentModel.id == document_id,
                DocumentModel.workspace_id == workspace_id,
                DocumentModel.status == DocumentStatus.ACTIVE.value,
                DocumentVersionModel.id == version_id,
                DocumentVersionModel.workspace_id == workspace_id,
            )
        )
        if exists is None:
            raise ResourceNotFoundError()
        chunks = (
            await self._session.scalars(
                select(ChunkModel)
                .where(
                    ChunkModel.workspace_id == workspace_id,
                    ChunkModel.document_version_id == version_id,
                )
                .order_by(ChunkModel.ordinal.asc())
            )
        ).all()
        return [self._chunk_record(chunk) for chunk in chunks]

    async def delete_document(
        self, actor: Actor, workspace_id: uuid.UUID, document_id: uuid.UUID, request_id: str
    ) -> None:
        document = await self._session.scalar(
            select(DocumentModel)
            .where(
                DocumentModel.id == document_id,
                DocumentModel.workspace_id == workspace_id,
                DocumentModel.status == DocumentStatus.ACTIVE.value,
            )
            .with_for_update()
        )
        if document is None:
            raise ResourceNotFoundError()
        document.status = DocumentStatus.DELETED.value
        document.deleted_at = datetime.now(UTC)
        document.version += 1
        await self._session.execute(
            update(DocumentVersionModel)
            .where(DocumentVersionModel.document_id == document_id)
            .values(active=False)
        )
        active_job_states = [
            IngestionJobState.PENDING.value,
            IngestionJobState.CLAIMED.value,
            IngestionJobState.VERIFYING.value,
            IngestionJobState.PARSING.value,
            IngestionJobState.NORMALIZING.value,
            IngestionJobState.CHUNKING.value,
            IngestionJobState.PUBLISHING.value,
            IngestionJobState.RETRY_WAIT.value,
        ]
        jobs = (
            await self._session.scalars(
                select(IngestionJobModel)
                .join(
                    DocumentVersionModel,
                    DocumentVersionModel.id == IngestionJobModel.document_version_id,
                )
                .where(
                    DocumentVersionModel.document_id == document_id,
                    IngestionJobModel.state.in_(active_job_states),
                )
                .with_for_update()
            )
        ).all()
        for job in jobs:
            prior = IngestionJobState(job.state)
            job.state = IngestionJobState.CANCEL_REQUESTED.value
            job.cancellation_requested = True
            job.version += 1
            await self._job_event(
                workspace_id,
                job.id,
                prior,
                IngestionJobState.CANCEL_REQUESTED,
                "document_deleted",
                {},
            )
        await self._audit(
            workspace_id, actor, "document.deleted", "document", document_id, request_id, {}
        )

    async def get_job(
        self, actor: Actor, workspace_id: uuid.UUID, job_id: uuid.UUID
    ) -> IngestionJobRecord | None:
        job = await self._session.scalar(
            select(IngestionJobModel).where(
                IngestionJobModel.id == job_id,
                IngestionJobModel.workspace_id == workspace_id,
            )
        )
        return None if job is None else self._job_record(job)

    async def cancel_job(
        self, actor: Actor, workspace_id: uuid.UUID, job_id: uuid.UUID, request_id: str
    ) -> IngestionJobRecord:
        job = await self._session.scalar(
            select(IngestionJobModel)
            .where(
                IngestionJobModel.id == job_id,
                IngestionJobModel.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        if job is None:
            raise ResourceNotFoundError()
        current = IngestionJobState(job.state)
        if current in {
            IngestionJobState.SUCCEEDED,
            IngestionJobState.CANCELLED,
            IngestionJobState.FAILED,
        }:
            return self._job_record(job)
        job.cancellation_requested = True
        job.state = IngestionJobState.CANCEL_REQUESTED.value
        job.version += 1
        await self._job_event(
            workspace_id, job.id, current, IngestionJobState.CANCEL_REQUESTED, "user_requested", {}
        )
        await self._audit(
            workspace_id,
            actor,
            "ingestion_job.cancel_requested",
            "ingestion_job",
            job.id,
            request_id,
            {},
        )
        return self._job_record(job)

    async def retry_job(
        self, actor: Actor, workspace_id: uuid.UUID, job_id: uuid.UUID, request_id: str
    ) -> IngestionJobRecord:
        job = await self._session.scalar(
            select(IngestionJobModel)
            .where(
                IngestionJobModel.id == job_id,
                IngestionJobModel.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        if job is None:
            raise ResourceNotFoundError()
        if IngestionJobState(job.state) not in {
            IngestionJobState.FAILED,
            IngestionJobState.RETRY_WAIT,
        }:
            raise ConflictError("Only failed or retry-wait ingestion jobs can be retried.")
        prior = IngestionJobState(job.state)
        job.state = IngestionJobState.PENDING.value
        job.error_class = None
        job.error_code = None
        job.error_message = None
        job.cancellation_requested = False
        job.next_attempt_at = datetime.now(UTC)
        job.version += 1
        await self._job_event(
            workspace_id, job.id, prior, IngestionJobState.PENDING, "user_retry", {}
        )
        await self._audit(
            workspace_id, actor, "ingestion_job.retried", "ingestion_job", job.id, request_id, {}
        )
        return self._job_record(job)

    async def active_embedding_set(
        self,
        workspace_id: uuid.UUID,
        *,
        provider: str,
        model: str,
        model_version: str,
        dimension: int,
        normalized: bool,
        config: dict[str, object],
    ) -> EmbeddingSetRecord:
        existing = await self._session.scalar(
            select(EmbeddingSetModel).where(
                EmbeddingSetModel.workspace_id == workspace_id,
                EmbeddingSetModel.provider == provider,
                EmbeddingSetModel.model == model,
                EmbeddingSetModel.model_version == model_version,
                EmbeddingSetModel.dimension == dimension,
                EmbeddingSetModel.normalized == normalized,
            )
        )
        if existing is None:
            existing = EmbeddingSetModel(
                workspace_id=workspace_id,
                provider=provider,
                model=model,
                model_version=model_version,
                dimension=dimension,
                normalized=normalized,
                config=config,
                status=EmbeddingSetStatus.ACTIVE.value,
            )
            self._session.add(existing)
            await self._session.flush()
        elif existing.status != EmbeddingSetStatus.ACTIVE.value:
            existing.status = EmbeddingSetStatus.ACTIVE.value
            existing.config = config
        return self._embedding_set_record(existing)

    async def semantic_search(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        embedding_set_id: uuid.UUID,
        query_vector: list[float],
        top_k: int,
        filters: SearchFilter,
    ) -> list[SearchCandidate]:
        statement = (
            select(
                ChunkEmbeddingModel,
                ChunkModel,
                DocumentVersionModel,
                DocumentModel,
                EmbeddingSetModel,
            )
            .join(ChunkModel, ChunkModel.id == ChunkEmbeddingModel.chunk_id)
            .join(
                DocumentVersionModel,
                DocumentVersionModel.id == ChunkEmbeddingModel.document_version_id,
            )
            .join(DocumentModel, DocumentModel.id == DocumentVersionModel.document_id)
            .join(EmbeddingSetModel, EmbeddingSetModel.id == ChunkEmbeddingModel.embedding_set_id)
            .where(
                ChunkEmbeddingModel.workspace_id == workspace_id,
                ChunkEmbeddingModel.embedding_set_id == embedding_set_id,
                ChunkEmbeddingModel.status == ChunkEmbeddingStatus.READY.value,
                ChunkModel.workspace_id == workspace_id,
                DocumentVersionModel.workspace_id == workspace_id,
                DocumentVersionModel.status == DocumentVersionStatus.READY.value,
                DocumentVersionModel.active.is_(True),
                DocumentModel.workspace_id == workspace_id,
                DocumentModel.status == DocumentStatus.ACTIVE.value,
                EmbeddingSetModel.workspace_id == workspace_id,
                EmbeddingSetModel.status == EmbeddingSetStatus.ACTIVE.value,
            )
        )
        if filters.source_id is not None:
            statement = statement.where(DocumentModel.source_id == filters.source_id)
        if filters.document_id is not None:
            statement = statement.where(DocumentModel.id == filters.document_id)
        rows = (await self._session.execute(statement)).all()
        candidates: list[SearchCandidate] = []
        for embedding, chunk, version, document, embedding_set in rows:
            if len(embedding.vector) != embedding_set.dimension:
                continue
            score = cosine_similarity(query_vector, [float(value) for value in embedding.vector])
            candidates.append(
                SearchCandidate(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    document_version_id=version.id,
                    source_id=document.source_id,
                    document_title=document.title,
                    ordinal=chunk.ordinal,
                    heading=chunk.heading,
                    block_type=chunk.block_type,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    snippet=self._snippet(chunk.text),
                    text=chunk.text,
                    distance=round(1.0 - score, 10),
                    score=round(score, 10),
                    retrieval_stage="semantic",
                    semantic_score=round(score, 10),
                    embedding_set_id=embedding_set.id,
                    embedding_provider=embedding_set.provider,
                    embedding_model=embedding_set.model,
                    embedding_model_version=embedding_set.model_version,
                )
            )
        ranked = sorted(candidates, key=lambda item: (-item.score, item.chunk_id.hex))[:top_k]
        return [replace(item, semantic_rank=index) for index, item in enumerate(ranked, start=1)]

    async def lexical_search(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        query: str,
        top_k: int,
        filters: SearchFilter,
        language: str,
    ) -> list[SearchCandidate]:
        query_expression = func.websearch_to_tsquery(language, query)
        vector_expression = func.to_tsvector(language, ChunkModel.text)
        rank_expression = func.ts_rank_cd(vector_expression, query_expression)
        statement = (
            select(
                ChunkModel,
                DocumentVersionModel,
                DocumentModel,
                rank_expression.label("lexical_score"),
            )
            .join(
                DocumentVersionModel,
                DocumentVersionModel.id == ChunkModel.document_version_id,
            )
            .join(DocumentModel, DocumentModel.id == DocumentVersionModel.document_id)
            .where(
                ChunkModel.workspace_id == workspace_id,
                DocumentVersionModel.workspace_id == workspace_id,
                DocumentVersionModel.status == DocumentVersionStatus.READY.value,
                DocumentVersionModel.active.is_(True),
                DocumentModel.workspace_id == workspace_id,
                DocumentModel.status == DocumentStatus.ACTIVE.value,
                vector_expression.op("@@")(query_expression),
            )
            .order_by(rank_expression.desc(), ChunkModel.id.asc())
            .limit(top_k)
        )
        if filters.source_id is not None:
            statement = statement.where(DocumentModel.source_id == filters.source_id)
        if filters.document_id is not None:
            statement = statement.where(DocumentModel.id == filters.document_id)
        rows = (await self._session.execute(statement)).all()
        return [
            SearchCandidate(
                chunk_id=chunk.id,
                document_id=document.id,
                document_version_id=version.id,
                source_id=document.source_id,
                document_title=document.title,
                ordinal=chunk.ordinal,
                heading=chunk.heading,
                block_type=chunk.block_type,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                snippet=self._snippet(chunk.text),
                text=chunk.text,
                distance=round(1.0 - float(lexical_score), 10),
                score=round(float(lexical_score), 10),
                retrieval_stage="lexical",
                lexical_score=round(float(lexical_score), 10),
                lexical_rank=index,
            )
            for index, (chunk, version, document, lexical_score) in enumerate(rows, start=1)
        ]

    async def create_answer_run(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        query: str,
        status: AnswerRunStatus,
        answer_text: str,
        retrieval_mode: str,
        retrieval_config_version: str,
        generation_provider: str,
        generation_model: str,
        generation_model_version: str,
        prompt_version: str,
        grounding_status: str,
        warnings: list[str],
        input_tokens: int,
        output_tokens: int,
        total_cost_usd: float,
        latency_ms: int,
        evidence: list[AnswerEvidenceDraft],
        citations: list[CitationDraft],
    ) -> AnswerRunRecord:
        answer = AnswerRunModel(
            workspace_id=workspace_id,
            created_by_user_id=actor.user_id,
            query_text=query,
            status=status.value,
            answer_text=answer_text,
            retrieval_mode=retrieval_mode,
            retrieval_config_version=retrieval_config_version,
            generation_provider=generation_provider,
            generation_model=generation_model,
            generation_model_version=generation_model_version,
            prompt_version=prompt_version,
            grounding_status=grounding_status,
            warnings=warnings,
            context_config={
                "evidence_count": len(evidence),
                "query_persisted": True,
                "content_telemetry": False,
            },
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost_usd=total_cost_usd,
            latency_ms=latency_ms,
        )
        self._session.add(answer)
        await self._session.flush()

        evidence_by_rank: dict[int, AnswerEvidenceModel] = {}
        for item in evidence:
            model = AnswerEvidenceModel(
                workspace_id=workspace_id,
                answer_run_id=answer.id,
                chunk_id=item.candidate.chunk_id,
                document_id=item.candidate.document_id,
                document_version_id=item.candidate.document_version_id,
                source_id=item.candidate.source_id,
                rank=item.rank,
                document_title=item.candidate.document_title,
                retrieval_stage=item.candidate.retrieval_stage,
                retrieval_score=item.candidate.score,
                semantic_score=item.candidate.semantic_score,
                lexical_score=item.candidate.lexical_score,
                rrf_score=item.candidate.rrf_score,
                quote=item.context_text,
                start_char=item.candidate.start_char,
                end_char=item.candidate.start_char + len(item.context_text),
            )
            self._session.add(model)
            evidence_by_rank[item.rank] = model
        await self._session.flush()

        for citation in citations:
            evidence_model = evidence_by_rank.get(citation.evidence_rank)
            if evidence_model is None:
                raise ConflictError("Citation references unknown answer evidence.")
            offset = evidence_model.quote.find(citation.quote)
            if offset < 0:
                raise ConflictError("Citation quote does not exist in answer evidence.")
            self._session.add(
                CitationModel(
                    workspace_id=workspace_id,
                    answer_run_id=answer.id,
                    answer_evidence_id=evidence_model.id,
                    marker=citation.marker,
                    answer_start_char=citation.answer_start_char,
                    answer_end_char=citation.answer_end_char,
                    evidence_start_char=evidence_model.start_char + offset,
                    evidence_end_char=evidence_model.start_char + offset + len(citation.quote),
                    quote=citation.quote,
                    status=CitationValidationStatus.VERIFIED.value,
                )
            )
        await self._session.flush()
        record = await self.get_answer_run(workspace_id=workspace_id, answer_run_id=answer.id)
        if record is None:
            raise ConflictError("The answer run could not be reloaded.")
        return record

    async def get_answer_run(
        self,
        *,
        workspace_id: uuid.UUID,
        answer_run_id: uuid.UUID,
    ) -> AnswerRunRecord | None:
        answer = await self._session.scalar(
            select(AnswerRunModel).where(
                AnswerRunModel.workspace_id == workspace_id,
                AnswerRunModel.id == answer_run_id,
            )
        )
        if answer is None:
            return None
        evidence_rows = (
            await self._session.scalars(
                select(AnswerEvidenceModel)
                .where(
                    AnswerEvidenceModel.workspace_id == workspace_id,
                    AnswerEvidenceModel.answer_run_id == answer_run_id,
                )
                .order_by(AnswerEvidenceModel.rank.asc(), AnswerEvidenceModel.id.asc())
            )
        ).all()
        citation_rows = (
            await self._session.scalars(
                select(CitationModel)
                .where(
                    CitationModel.workspace_id == workspace_id,
                    CitationModel.answer_run_id == answer_run_id,
                )
                .order_by(CitationModel.answer_start_char.asc(), CitationModel.id.asc())
            )
        ).all()
        evidence_by_id = {item.id: item for item in evidence_rows}
        return self._answer_run_record(
            answer, list(evidence_rows), list(citation_rows), evidence_by_id
        )

    async def embedding_coverage(
        self, workspace_id: uuid.UUID, embedding_set_id: uuid.UUID
    ) -> EmbeddingCoverageRecord:
        total = await self._session.scalar(
            select(func.count(ChunkModel.id))
            .join(DocumentVersionModel, DocumentVersionModel.id == ChunkModel.document_version_id)
            .join(DocumentModel, DocumentModel.id == DocumentVersionModel.document_id)
            .where(
                ChunkModel.workspace_id == workspace_id,
                DocumentVersionModel.workspace_id == workspace_id,
                DocumentVersionModel.status == DocumentVersionStatus.READY.value,
                DocumentVersionModel.active.is_(True),
                DocumentModel.workspace_id == workspace_id,
                DocumentModel.status == DocumentStatus.ACTIVE.value,
            )
        )
        embedded = await self._session.scalar(
            select(func.count(ChunkEmbeddingModel.id))
            .join(ChunkModel, ChunkModel.id == ChunkEmbeddingModel.chunk_id)
            .join(DocumentVersionModel, DocumentVersionModel.id == ChunkModel.document_version_id)
            .join(DocumentModel, DocumentModel.id == DocumentVersionModel.document_id)
            .where(
                ChunkEmbeddingModel.workspace_id == workspace_id,
                ChunkEmbeddingModel.embedding_set_id == embedding_set_id,
                ChunkEmbeddingModel.status == ChunkEmbeddingStatus.READY.value,
                DocumentVersionModel.workspace_id == workspace_id,
                DocumentVersionModel.status == DocumentVersionStatus.READY.value,
                DocumentVersionModel.active.is_(True),
                DocumentModel.workspace_id == workspace_id,
                DocumentModel.status == DocumentStatus.ACTIVE.value,
            )
        )
        return EmbeddingCoverageRecord(
            workspace_id=workspace_id,
            embedding_set_id=embedding_set_id,
            total_ready_chunks=int(total or 0),
            embedded_ready_chunks=int(embedded or 0),
        )

    async def list_missing_embedding_chunks(
        self, workspace_id: uuid.UUID, embedding_set_id: uuid.UUID, *, limit: int
    ) -> list[MissingEmbeddingChunkRecord]:
        rows = (
            await self._session.scalars(
                select(ChunkModel)
                .join(
                    DocumentVersionModel, DocumentVersionModel.id == ChunkModel.document_version_id
                )
                .join(DocumentModel, DocumentModel.id == DocumentVersionModel.document_id)
                .outerjoin(
                    ChunkEmbeddingModel,
                    and_(
                        ChunkEmbeddingModel.chunk_id == ChunkModel.id,
                        ChunkEmbeddingModel.embedding_set_id == embedding_set_id,
                    ),
                )
                .where(
                    ChunkModel.workspace_id == workspace_id,
                    ChunkEmbeddingModel.id.is_(None),
                    DocumentVersionModel.workspace_id == workspace_id,
                    DocumentVersionModel.status == DocumentVersionStatus.READY.value,
                    DocumentVersionModel.active.is_(True),
                    DocumentModel.workspace_id == workspace_id,
                    DocumentModel.status == DocumentStatus.ACTIVE.value,
                )
                .order_by(ChunkModel.document_version_id.asc(), ChunkModel.ordinal.asc())
                .limit(limit)
            )
        ).all()
        return [
            MissingEmbeddingChunkRecord(
                chunk_id=row.id,
                document_version_id=row.document_version_id,
                ordinal=row.ordinal,
                text=row.text,
            )
            for row in rows
        ]

    async def write_chunk_embeddings(
        self,
        workspace_id: uuid.UUID,
        embedding_set_id: uuid.UUID,
        embeddings: list[ChunkEmbeddingWriteRecord],
    ) -> int:
        if not embeddings:
            return 0
        existing = set(
            (
                await self._session.scalars(
                    select(ChunkEmbeddingModel.chunk_id).where(
                        ChunkEmbeddingModel.workspace_id == workspace_id,
                        ChunkEmbeddingModel.embedding_set_id == embedding_set_id,
                        ChunkEmbeddingModel.chunk_id.in_([item.chunk_id for item in embeddings]),
                    )
                )
            ).all()
        )
        written = 0
        for embedding in embeddings:
            if embedding.chunk_id in existing:
                continue
            self._session.add(
                ChunkEmbeddingModel(
                    workspace_id=workspace_id,
                    chunk_id=embedding.chunk_id,
                    document_version_id=embedding.document_version_id,
                    embedding_set_id=embedding_set_id,
                    vector=embedding.vector,
                    status=ChunkEmbeddingStatus.READY.value,
                    token_count=embedding.token_count,
                )
            )
            written += 1
        await self._session.flush()
        return written

    async def _document_record(self, document: DocumentModel) -> DocumentRecord:
        latest_version = await self._session.scalar(
            select(DocumentVersionModel)
            .where(DocumentVersionModel.document_id == document.id)
            .order_by(
                DocumentVersionModel.version_number.desc(), DocumentVersionModel.created_at.desc()
            )
            .limit(1)
        )
        latest_job = None
        if latest_version is not None:
            latest_job = await self._session.scalar(
                select(IngestionJobModel)
                .where(IngestionJobModel.document_version_id == latest_version.id)
                .order_by(IngestionJobModel.created_at.desc())
                .limit(1)
            )
        return DocumentRecord(
            id=document.id,
            workspace_id=document.workspace_id,
            source_id=document.source_id,
            title=document.title,
            status=DocumentStatus(document.status),
            version=document.version,
            latest_version_id=latest_version.id if latest_version is not None else None,
            latest_version_status=(
                DocumentVersionStatus(latest_version.status) if latest_version is not None else None
            ),
            latest_job_id=latest_job.id if latest_job is not None else None,
        )

    async def _records_from_response(
        self, body: dict[str, str]
    ) -> tuple[DocumentRecord, DocumentVersionRecord, IngestionJobRecord]:
        document = await self._session.get(DocumentModel, uuid.UUID(body["document_id"]))
        version = await self._session.get(
            DocumentVersionModel, uuid.UUID(body["document_version_id"])
        )
        job = await self._session.get(IngestionJobModel, uuid.UUID(body["ingestion_job_id"]))
        if document is None or version is None or job is None:
            raise ConflictError("The idempotent response can no longer be resolved.")
        document_record = await self._document_record(document)
        return document_record, self._version_record(version), self._job_record(job)

    @staticmethod
    def _response_body(
        document: DocumentRecord, version: DocumentVersionRecord, job: IngestionJobRecord
    ) -> dict[str, str]:
        return {
            "document_id": str(document.id),
            "document_version_id": str(version.id),
            "ingestion_job_id": str(job.id),
        }

    @staticmethod
    def _source_record(source: SourceModel) -> SourceRecord:
        return SourceRecord(
            id=source.id,
            workspace_id=source.workspace_id,
            name=source.name,
            source_type=SourceType(source.source_type),
            status=SourceStatus(source.status),
            version=source.version,
        )

    @staticmethod
    def _upload_intent_record(intent: UploadIntentModel) -> UploadIntentRecord:
        return UploadIntentRecord(
            id=intent.id,
            workspace_id=intent.workspace_id,
            created_by_user_id=intent.created_by_user_id,
            object_key=intent.object_key,
            original_filename=intent.original_filename,
            media_type=intent.media_type,
            byte_size=intent.byte_size,
            digest_sha256=intent.digest_sha256,
            status=UploadIntentStatus(intent.status),
            expires_at=intent.expires_at,
        )

    @staticmethod
    def _version_record(version: DocumentVersionModel) -> DocumentVersionRecord:
        return DocumentVersionRecord(
            id=version.id,
            workspace_id=version.workspace_id,
            document_id=version.document_id,
            version_number=version.version_number,
            object_key=version.object_key,
            digest_sha256=version.digest_sha256,
            media_type=version.media_type,
            byte_size=version.byte_size,
            status=DocumentVersionStatus(version.status),
            active=version.active,
            created_at=version.created_at,
            parser_name=version.parser_name,
            parser_version=version.parser_version,
            chunker_name=version.chunker_name,
            chunker_version=version.chunker_version,
            normalized_object_key=version.normalized_object_key,
            normalized_digest_sha256=version.normalized_digest_sha256,
            chunk_count=version.chunk_count,
            character_count=version.character_count,
            token_count=version.token_count,
            embedding_set_id=version.embedding_set_id,
            embedding_count=version.embedding_count,
            safe_metadata=version.safe_metadata,
        )

    @staticmethod
    def _chunk_record(chunk: ChunkModel) -> ChunkRecord:
        return ChunkRecord(
            id=chunk.id,
            workspace_id=chunk.workspace_id,
            document_version_id=chunk.document_version_id,
            ordinal=chunk.ordinal,
            block_type=chunk.block_type,
            heading=chunk.heading,
            page_number=chunk.page_number,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
            token_count=chunk.token_count,
            content_hash=chunk.content_hash,
            text=chunk.text,
            safe_metadata=chunk.safe_metadata,
            created_at=chunk.created_at,
        )

    @staticmethod
    def _answer_run_record(
        answer: AnswerRunModel,
        evidence_rows: list[AnswerEvidenceModel],
        citation_rows: list[CitationModel],
        evidence_by_id: dict[uuid.UUID, AnswerEvidenceModel],
    ) -> AnswerRunRecord:
        evidence = [
            AnswerEvidenceRecord(
                id=item.id,
                rank=item.rank,
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                document_version_id=item.document_version_id,
                source_id=item.source_id,
                document_title=item.document_title,
                retrieval_stage=item.retrieval_stage,
                retrieval_score=item.retrieval_score,
                semantic_score=item.semantic_score,
                lexical_score=item.lexical_score,
                rrf_score=item.rrf_score,
                quote=item.quote,
                start_char=item.start_char,
                end_char=item.end_char,
            )
            for item in evidence_rows
        ]
        citations: list[ValidatedCitationRecord] = []
        for item in citation_rows:
            evidence_item = evidence_by_id[item.answer_evidence_id]
            citations.append(
                ValidatedCitationRecord(
                    id=item.id,
                    marker=item.marker,
                    evidence_rank=evidence_item.rank,
                    answer_evidence_id=item.answer_evidence_id,
                    chunk_id=evidence_item.chunk_id,
                    document_id=evidence_item.document_id,
                    document_version_id=evidence_item.document_version_id,
                    quote=item.quote,
                    evidence_start_char=item.evidence_start_char,
                    evidence_end_char=item.evidence_end_char,
                    answer_start_char=item.answer_start_char,
                    answer_end_char=item.answer_end_char,
                    status=CitationValidationStatus(item.status),
                )
            )
        return AnswerRunRecord(
            id=answer.id,
            workspace_id=answer.workspace_id,
            created_by_user_id=answer.created_by_user_id,
            status=AnswerRunStatus(answer.status),
            query=answer.query_text,
            answer_text=answer.answer_text,
            retrieval_mode=answer.retrieval_mode,
            retrieval_config_version=answer.retrieval_config_version,
            generation_provider=answer.generation_provider,
            generation_model=answer.generation_model,
            generation_model_version=answer.generation_model_version,
            prompt_version=answer.prompt_version,
            grounding_status=answer.grounding_status,
            warnings=list(answer.warnings),
            input_tokens=answer.input_tokens,
            output_tokens=answer.output_tokens,
            total_cost_usd=answer.total_cost_usd,
            latency_ms=answer.latency_ms,
            evidence=evidence,
            citations=citations,
            created_at=answer.created_at,
        )

    @staticmethod
    def _embedding_set_record(embedding_set: EmbeddingSetModel) -> EmbeddingSetRecord:
        return EmbeddingSetRecord(
            id=embedding_set.id,
            workspace_id=embedding_set.workspace_id,
            provider=embedding_set.provider,
            model=embedding_set.model,
            model_version=embedding_set.model_version,
            dimension=embedding_set.dimension,
            normalized=embedding_set.normalized,
            config=embedding_set.config,
            status=EmbeddingSetStatus(embedding_set.status),
            created_at=embedding_set.created_at,
        )

    @staticmethod
    def _snippet(text_value: str) -> str:
        collapsed = " ".join(text_value.split())
        return collapsed[:240] + ("…" if len(collapsed) > 240 else "")

    @staticmethod
    def _job_record(job: IngestionJobModel) -> IngestionJobRecord:
        return IngestionJobRecord(
            id=job.id,
            workspace_id=job.workspace_id,
            document_version_id=job.document_version_id,
            state=IngestionJobState(job.state),
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            lease_owner=job.lease_owner,
            lease_expires_at=job.lease_expires_at,
            heartbeat_at=job.heartbeat_at,
            progress=job.progress,
            error_class=job.error_class,
            error_code=job.error_code,
            error_message=job.error_message,
            cancellation_requested=job.cancellation_requested,
            next_attempt_at=job.next_attempt_at,
            version=job.version,
            created_at=job.created_at,
        )

    async def _audit(
        self,
        workspace_id: uuid.UUID,
        actor: Actor,
        action: str,
        target_type: str,
        target_id: uuid.UUID,
        request_id: str,
        safe_metadata: dict[str, str],
    ) -> None:
        self._session.add(
            AuditEventModel(
                workspace_id=workspace_id,
                actor_user_id=actor.user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                request_id=request_id,
                safe_metadata=safe_metadata,
            )
        )

    async def _job_event(
        self,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
        from_state: IngestionJobState | None,
        to_state: IngestionJobState,
        reason: str,
        safe_metadata: dict[str, str],
    ) -> None:
        self._session.add(
            JobEventModel(
                workspace_id=workspace_id,
                job_id=job_id,
                from_state=from_state.value if from_state is not None else None,
                to_state=to_state.value,
                reason=reason,
                safe_metadata=safe_metadata,
            )
        )


class SqlAlchemyIngestionJobStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim_next_job(
        self, worker_id: str, *, lease_seconds: int = 60
    ) -> IngestionJobRecord | None:
        now = datetime.now(UTC)
        claimable_states = [IngestionJobState.PENDING.value, IngestionJobState.RETRY_WAIT.value]
        job = await self._session.scalar(
            select(IngestionJobModel)
            .where(
                or_(
                    and_(
                        IngestionJobModel.state.in_(claimable_states),
                        IngestionJobModel.next_attempt_at <= now,
                    ),
                    and_(
                        IngestionJobModel.state.in_(
                            [
                                IngestionJobState.CLAIMED.value,
                                IngestionJobState.VERIFYING.value,
                                IngestionJobState.PARSING.value,
                                IngestionJobState.NORMALIZING.value,
                                IngestionJobState.CHUNKING.value,
                                IngestionJobState.EMBEDDING.value,
                                IngestionJobState.PUBLISHING.value,
                            ]
                        ),
                        IngestionJobModel.lease_expires_at < now,
                    ),
                    IngestionJobModel.state == IngestionJobState.CANCEL_REQUESTED.value,
                ),
                IngestionJobModel.attempts < IngestionJobModel.max_attempts,
            )
            .order_by(IngestionJobModel.created_at.asc(), IngestionJobModel.id.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return None
        prior = IngestionJobState(job.state)
        if job.state != IngestionJobState.CANCEL_REQUESTED.value:
            job.attempts += 1
        job.state = IngestionJobState.CLAIMED.value
        job.lease_owner = worker_id
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.heartbeat_at = now
        job.progress = max(job.progress, 5)
        job.version += 1
        await self._job_event(
            job.workspace_id, job.id, prior, IngestionJobState.CLAIMED, "claimed", {}
        )
        return SqlAlchemyDocumentStore._job_record(job)

    async def transition_job(
        self,
        job_id: uuid.UUID,
        worker_id: str,
        expected_version: int,
        to_state: IngestionJobState,
        *,
        progress: int,
        reason: str,
        error_class: RetryClass | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> IngestionJobRecord:
        now = datetime.now(UTC)
        job = await self._session.scalar(
            select(IngestionJobModel).where(IngestionJobModel.id == job_id).with_for_update()
        )
        if job is None:
            raise ResourceNotFoundError()
        if job.lease_owner != worker_id or job.version != expected_version:
            raise ConflictError("The ingestion job lease is no longer valid.")
        if job.lease_expires_at is not None and job.lease_expires_at < now:
            raise ConflictError("The ingestion job lease has expired.")
        prior = IngestionJobState(job.state)
        job.state = to_state.value
        job.progress = progress
        job.error_class = error_class.value if error_class is not None else None
        job.error_code = error_code
        job.error_message = error_message
        job.heartbeat_at = now
        job.version += 1
        if to_state in {
            IngestionJobState.SUCCEEDED,
            IngestionJobState.CANCELLED,
            IngestionJobState.FAILED,
        }:
            job.lease_owner = None
            job.lease_expires_at = None
        if to_state == IngestionJobState.RETRY_WAIT:
            job.lease_owner = None
            job.lease_expires_at = None
            job.next_attempt_at = now + timedelta(seconds=retry_after_seconds or 30)
        version_status_by_state = {
            IngestionJobState.VERIFYING: DocumentVersionStatus.VERIFYING,
            IngestionJobState.PARSING: DocumentVersionStatus.PARSING,
            IngestionJobState.NORMALIZING: DocumentVersionStatus.NORMALIZING,
            IngestionJobState.CHUNKING: DocumentVersionStatus.CHUNKING,
            IngestionJobState.EMBEDDING: DocumentVersionStatus.EMBEDDING,
            IngestionJobState.CANCELLED: DocumentVersionStatus.CANCELLED,
            IngestionJobState.FAILED: DocumentVersionStatus.FAILED,
        }
        next_version_status = version_status_by_state.get(to_state)
        if next_version_status is not None:
            version = await self._session.scalar(
                select(DocumentVersionModel)
                .where(DocumentVersionModel.id == job.document_version_id)
                .with_for_update()
            )
            if version is not None:
                version.status = next_version_status.value
                version.error_code = error_code
                version.error_message = error_message
        await self._job_event(job.workspace_id, job.id, prior, to_state, reason, {})
        return SqlAlchemyDocumentStore._job_record(job)

    async def publish_document_version(
        self,
        job_id: uuid.UUID,
        worker_id: str,
        expected_job_version: int,
        *,
        chunks: Sequence[ChunkDraftRecord] = (),
        embedding_set: EmbeddingSetRecord | None = None,
        embeddings: Sequence[ChunkEmbeddingDraftRecord] = (),
        parser_name: str | None = None,
        parser_version: str | None = None,
        chunker_name: str | None = None,
        chunker_version: str | None = None,
        normalized_object_key: str | None = None,
        normalized_digest_sha256: str | None = None,
        character_count: int = 0,
        token_count: int = 0,
        safe_metadata: dict[str, object] | None = None,
    ) -> IngestionJobRecord:
        now = datetime.now(UTC)
        job = await self._session.scalar(
            select(IngestionJobModel).where(IngestionJobModel.id == job_id).with_for_update()
        )
        if job is None:
            raise ResourceNotFoundError()
        if job.lease_owner != worker_id or job.version != expected_job_version:
            raise ConflictError("The ingestion job lease is no longer valid.")
        if job.lease_expires_at is not None and job.lease_expires_at < now:
            raise ConflictError("The ingestion job lease has expired.")
        version = await self._session.scalar(
            select(DocumentVersionModel)
            .where(DocumentVersionModel.id == job.document_version_id)
            .with_for_update()
        )
        if version is None:
            raise ResourceNotFoundError()
        if chunks:
            await self._session.execute(
                delete(ChunkModel).where(ChunkModel.document_version_id == version.id)
            )
            chunks_by_ordinal: dict[int, ChunkModel] = {}
            for chunk in chunks:
                row = ChunkModel(
                    workspace_id=version.workspace_id,
                    document_version_id=version.id,
                    ordinal=chunk.ordinal,
                    block_type=chunk.block_type,
                    heading=chunk.heading,
                    page_number=chunk.page_number,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    token_count=chunk.token_count,
                    content_hash=chunk.content_hash,
                    text=chunk.text,
                    safe_metadata=chunk.safe_metadata,
                )
                self._session.add(row)
                chunks_by_ordinal[chunk.ordinal] = row
            await self._session.flush()
            if embedding_set is None or len(embeddings) != len(chunks):
                raise ConflictError("Document publication requires complete embeddings.")
            embeddings_by_ordinal = {item.chunk_ordinal: item for item in embeddings}
            if set(embeddings_by_ordinal) != set(chunks_by_ordinal):
                raise ConflictError("Embedding ordinals do not match published chunks.")
            for embedding in embeddings:
                if len(embedding.vector) != embedding_set.dimension:
                    raise ConflictError("Embedding vector dimension does not match its set.")
                chunk_row = chunks_by_ordinal[embedding.chunk_ordinal]
                self._session.add(
                    ChunkEmbeddingModel(
                        workspace_id=version.workspace_id,
                        chunk_id=chunk_row.id,
                        document_version_id=version.id,
                        embedding_set_id=embedding_set.id,
                        vector=embedding.vector,
                        status=ChunkEmbeddingStatus.READY.value,
                        token_count=embedding.token_count,
                    )
                )
            version.parser_name = parser_name
            version.parser_version = parser_version
            version.chunker_name = chunker_name
            version.chunker_version = chunker_version
            version.normalized_object_key = normalized_object_key
            version.normalized_digest_sha256 = normalized_digest_sha256
            version.chunk_count = len(chunks)
            version.embedding_set_id = embedding_set.id
            version.embedding_count = len(embeddings)
            version.character_count = character_count
            version.token_count = token_count
            version.safe_metadata = safe_metadata or {}
        await self._session.execute(
            update(DocumentVersionModel)
            .where(DocumentVersionModel.document_id == version.document_id)
            .values(active=False)
        )
        prior = IngestionJobState(job.state)
        version.active = True
        version.status = DocumentVersionStatus.READY.value
        job.state = IngestionJobState.SUCCEEDED.value
        job.progress = 100
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = now
        job.error_class = None
        job.error_code = None
        job.error_message = None
        job.version += 1
        await self._job_event(
            job.workspace_id, job.id, prior, IngestionJobState.SUCCEEDED, "published", {}
        )
        return SqlAlchemyDocumentStore._job_record(job)

    async def document_version_for_job(self, job_id: uuid.UUID) -> DocumentVersionRecord | None:
        row = await self._session.scalar(
            select(DocumentVersionModel)
            .join(
                IngestionJobModel, IngestionJobModel.document_version_id == DocumentVersionModel.id
            )
            .where(IngestionJobModel.id == job_id)
        )
        return None if row is None else SqlAlchemyDocumentStore._version_record(row)

    async def _job_event(
        self,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
        from_state: IngestionJobState | None,
        to_state: IngestionJobState,
        reason: str,
        safe_metadata: dict[str, str],
    ) -> None:
        self._session.add(
            JobEventModel(
                workspace_id=workspace_id,
                job_id=job_id,
                from_state=from_state.value if from_state is not None else None,
                to_state=to_state.value,
                reason=reason,
                safe_metadata=safe_metadata,
            )
        )


class SqlAlchemyTransaction:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self.workspaces: WorkspaceStore
        self.documents: DocumentStore

    async def __aenter__(self) -> SqlAlchemyTransaction:
        self._session = self._session_factory()
        await self._session.begin()
        self.workspaces = SqlAlchemyWorkspaceStore(self._session)
        self.documents = SqlAlchemyDocumentStore(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        try:
            if exc_type is None:
                await self._session.commit()
            else:
                await self._session.rollback()
        finally:
            await self._session.close()


class SqlAlchemyTransactionFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> Transaction:
        return SqlAlchemyTransaction(self._session_factory)
