from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from atlas_api.application.ports import (
    ChunkRecord,
    DocumentRecord,
    DocumentVersionRecord,
    EmbeddingBackfillResult,
    IngestionJobRecord,
    MemberRecord,
    SemanticSearchCandidate,
    SourceRecord,
    UploadIntentRecord,
    WorkspaceRecord,
)
from atlas_api.domain.models import (
    Actor,
    DocumentStatus,
    DocumentVersionStatus,
    IngestionJobState,
    Role,
    SourceStatus,
    SourceType,
    UploadIntentStatus,
)


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str

    @classmethod
    def from_actor(cls, actor: Actor) -> MeResponse:
        return cls(id=actor.user_id, email=actor.email, display_name=actor.display_name)


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("name must contain at least two visible characters")
        return normalized


class WorkspaceUpdate(WorkspaceCreate):
    version: int = Field(ge=1)


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    role: Role

    @classmethod
    def from_record(cls, record: WorkspaceRecord) -> WorkspaceResponse:
        return cls(id=record.id, name=record.name, version=record.version, role=record.role)


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceResponse]


class MemberCreate(BaseModel):
    email: EmailStr
    role: Role = Role.MEMBER


class MemberUpdate(BaseModel):
    role: Role
    version: int = Field(ge=1)


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    email: str
    display_name: str
    role: Role
    version: int

    @classmethod
    def from_record(cls, record: MemberRecord) -> MemberResponse:
        return cls(
            user_id=record.user_id,
            email=record.email,
            display_name=record.display_name,
            role=record.role,
            version=record.version,
        )


class MemberListResponse(BaseModel):
    items: list[MemberResponse]


class SourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)


class SourceResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    source_type: SourceType
    status: SourceStatus
    version: int

    @classmethod
    def from_record(cls, record: SourceRecord) -> SourceResponse:
        return cls(
            id=record.id,
            workspace_id=record.workspace_id,
            name=record.name,
            source_type=record.source_type,
            status=record.status,
            version=record.version,
        )


class SourceListResponse(BaseModel):
    items: list[SourceResponse]


class UploadIntentCreate(BaseModel):
    original_filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=3, max_length=255)
    byte_size: int = Field(gt=0)
    digest_sha256: str = Field(min_length=64, max_length=64)


class UploadIntentResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    object_key: str
    original_filename: str
    media_type: str
    byte_size: int
    digest_sha256: str
    status: UploadIntentStatus
    expires_at: str
    upload_url: str | None = None

    @classmethod
    def from_record(cls, record: UploadIntentRecord) -> UploadIntentResponse:
        return cls(
            id=record.id,
            workspace_id=record.workspace_id,
            object_key=record.object_key,
            original_filename=record.original_filename,
            media_type=record.media_type,
            byte_size=record.byte_size,
            digest_sha256=record.digest_sha256,
            status=record.status,
            expires_at=record.expires_at.isoformat(),
            upload_url=record.upload_url,
        )


class UploadFinalize(BaseModel):
    source_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)


class DocumentResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    source_id: uuid.UUID
    title: str
    status: DocumentStatus
    version: int
    latest_version_id: uuid.UUID | None
    latest_version_status: DocumentVersionStatus | None
    latest_job_id: uuid.UUID | None

    @classmethod
    def from_record(cls, record: DocumentRecord) -> DocumentResponse:
        return cls(
            id=record.id,
            workspace_id=record.workspace_id,
            source_id=record.source_id,
            title=record.title,
            status=record.status,
            version=record.version,
            latest_version_id=record.latest_version_id,
            latest_version_status=record.latest_version_status,
            latest_job_id=record.latest_job_id,
        )


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]


class DocumentVersionResponse(BaseModel):
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
    created_at: str
    parser_name: str | None = None
    parser_version: str | None = None
    chunker_name: str | None = None
    chunker_version: str | None = None
    normalized_object_key: str | None = None
    normalized_digest_sha256: str | None = None
    chunk_count: int = 0
    character_count: int = 0
    token_count: int = 0
    safe_metadata: dict[str, object] = Field(default_factory=dict)
    embedding_set_id: uuid.UUID | None = None
    embedding_count: int = 0

    @classmethod
    def from_record(cls, record: DocumentVersionRecord) -> DocumentVersionResponse:
        return cls(
            id=record.id,
            workspace_id=record.workspace_id,
            document_id=record.document_id,
            version_number=record.version_number,
            object_key=record.object_key,
            digest_sha256=record.digest_sha256,
            media_type=record.media_type,
            byte_size=record.byte_size,
            status=record.status,
            active=record.active,
            created_at=record.created_at.isoformat(),
            parser_name=record.parser_name,
            parser_version=record.parser_version,
            chunker_name=record.chunker_name,
            chunker_version=record.chunker_version,
            normalized_object_key=record.normalized_object_key,
            normalized_digest_sha256=record.normalized_digest_sha256,
            chunk_count=record.chunk_count,
            character_count=record.character_count,
            token_count=record.token_count,
            embedding_set_id=record.embedding_set_id,
            embedding_count=record.embedding_count,
            safe_metadata=record.safe_metadata or {},
        )


class DocumentVersionListResponse(BaseModel):
    items: list[DocumentVersionResponse]


class ChunkResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    document_version_id: uuid.UUID
    ordinal: int
    block_type: str
    heading: str | None
    page_number: int | None
    start_char: int
    end_char: int
    token_count: int
    content_hash: str
    text: str
    safe_metadata: dict[str, object]
    created_at: str

    @classmethod
    def from_record(cls, record: ChunkRecord) -> ChunkResponse:
        return cls(
            id=record.id,
            workspace_id=record.workspace_id,
            document_version_id=record.document_version_id,
            ordinal=record.ordinal,
            block_type=record.block_type,
            heading=record.heading,
            page_number=record.page_number,
            start_char=record.start_char,
            end_char=record.end_char,
            token_count=record.token_count,
            content_hash=record.content_hash,
            text=record.text,
            safe_metadata=record.safe_metadata,
            created_at=record.created_at.isoformat(),
        )


class ChunkListResponse(BaseModel):
    items: list[ChunkResponse]


class IngestionJobResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    document_version_id: uuid.UUID
    state: IngestionJobState
    attempts: int
    max_attempts: int
    lease_owner: str | None
    lease_expires_at: str | None
    heartbeat_at: str | None
    progress: int
    error_class: str | None
    error_code: str | None
    error_message: str | None
    cancellation_requested: bool
    next_attempt_at: str
    version: int
    created_at: str

    @classmethod
    def from_record(cls, record: IngestionJobRecord) -> IngestionJobResponse:
        return cls(
            id=record.id,
            workspace_id=record.workspace_id,
            document_version_id=record.document_version_id,
            state=record.state,
            attempts=record.attempts,
            max_attempts=record.max_attempts,
            lease_owner=record.lease_owner,
            lease_expires_at=(
                record.lease_expires_at.isoformat() if record.lease_expires_at else None
            ),
            heartbeat_at=record.heartbeat_at.isoformat() if record.heartbeat_at else None,
            progress=record.progress,
            error_class=record.error_class,
            error_code=record.error_code,
            error_message=record.error_message,
            cancellation_requested=record.cancellation_requested,
            next_attempt_at=record.next_attempt_at.isoformat(),
            version=record.version,
            created_at=record.created_at.isoformat(),
        )


class UploadFinalizeResponse(BaseModel):
    document: DocumentResponse
    document_version: DocumentVersionResponse
    ingestion_job: IngestionJobResponse


class SemanticSearchFilters(BaseModel):
    source_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    filters: SemanticSearchFilters = Field(default_factory=SemanticSearchFilters)
    debug: bool = False


class EvidenceResponse(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    source_id: uuid.UUID
    document_title: str
    ordinal: int
    heading: str | None
    block_type: str
    start_char: int
    end_char: int
    snippet: str
    distance: float
    score: float
    embedding_set_id: uuid.UUID
    embedding_provider: str
    embedding_model: str
    embedding_model_version: str

    @classmethod
    def from_candidate(cls, candidate: SemanticSearchCandidate) -> EvidenceResponse:
        return cls(
            chunk_id=candidate.chunk_id,
            document_id=candidate.document_id,
            document_version_id=candidate.document_version_id,
            source_id=candidate.source_id,
            document_title=candidate.document_title,
            ordinal=candidate.ordinal,
            heading=candidate.heading,
            block_type=candidate.block_type,
            start_char=candidate.start_char,
            end_char=candidate.end_char,
            snippet=candidate.snippet,
            distance=candidate.distance,
            score=candidate.score,
            embedding_set_id=candidate.embedding_set_id,
            embedding_provider=candidate.embedding_provider,
            embedding_model=candidate.embedding_model,
            embedding_model_version=candidate.embedding_model_version,
        )


class SemanticSearchResponse(BaseModel):
    items: list[EvidenceResponse]
    trace_id: str
    debug: dict[str, object] | None = None


class EmbeddingBackfillRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)


class EmbeddingBackfillResponse(BaseModel):
    embedding_set_id: uuid.UUID
    missing_before: int
    embedded_count: int
    missing_after: int

    @classmethod
    def from_result(cls, result: EmbeddingBackfillResult) -> EmbeddingBackfillResponse:
        return cls(
            embedding_set_id=result.embedding_set_id,
            missing_before=result.missing_before,
            embedded_count=result.embedded_count,
            missing_after=result.missing_after,
        )


class HealthResponse(BaseModel):
    status: str
    service: str
