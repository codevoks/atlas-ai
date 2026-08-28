from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Permission(StrEnum):
    WORKSPACE_READ = "workspace:read"
    WORKSPACE_UPDATE = "workspace:update"
    MEMBER_LIST = "member:list"
    MEMBER_ADD = "member:add"
    MEMBER_UPDATE = "member:update"
    MEMBER_REMOVE = "member:remove"
    AUDIT_READ = "audit:read"
    SOURCE_READ = "source:read"
    SOURCE_CREATE = "source:create"
    DOCUMENT_READ = "document:read"
    DOCUMENT_CREATE = "document:create"
    DOCUMENT_DELETE = "document:delete"
    INGESTION_JOB_READ = "ingestion_job:read"
    INGESTION_JOB_MANAGE = "ingestion_job:manage"


class SourceType(StrEnum):
    UPLOAD = "upload"


class SourceStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class DocumentStatus(StrEnum):
    ACTIVE = "active"
    DELETED = "deleted"


class DocumentVersionStatus(StrEnum):
    UPLOAD_PENDING = "upload_pending"
    INGESTION_PENDING = "ingestion_pending"
    VERIFYING = "verifying"
    PARSING = "parsing"
    NORMALIZING = "normalizing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UploadIntentStatus(StrEnum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    FINALIZED = "finalized"
    EXPIRED = "expired"


class IngestionJobState(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    VERIFYING = "verifying"
    PARSING = "parsing"
    NORMALIZING = "normalizing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    PUBLISHING = "publishing"
    SUCCEEDED = "succeeded"
    RETRY_WAIT = "retry_wait"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    FAILED = "failed"


class RetryClass(StrEnum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    INTEGRITY = "integrity"
    CANCELLED = "cancelled"


class EmbeddingSetStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class ChunkEmbeddingStatus(StrEnum):
    READY = "ready"
    FAILED = "failed"


class AnswerRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUSED = "refused"


class CitationValidationStatus(StrEnum):
    VERIFIED = "verified"
    REJECTED = "rejected"


class EvaluationDatasetStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class EvaluationRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


class EvaluationResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    SYSTEM_FAILED = "system_failed"
    METRIC_FAILED = "metric_failed"
    MISSING_LABELS = "missing_labels"


@dataclass(frozen=True, slots=True)
class IdentityClaims:
    issuer: str
    subject: str
    email: str
    display_name: str


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: uuid.UUID
    issuer: str
    subject: str
    email: str
    display_name: str


@dataclass(frozen=True, slots=True)
class MembershipContext:
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: Role
    status: MembershipStatus
