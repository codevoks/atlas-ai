from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Literal, Protocol

from atlas_api.domain.models import (
    Actor,
    AnswerRunStatus,
    ApprovalStatus,
    ChunkEmbeddingStatus,
    CitationValidationStatus,
    DocumentStatus,
    DocumentVersionStatus,
    EmbeddingSetStatus,
    EvaluationDatasetStatus,
    EvaluationResultStatus,
    EvaluationRunStatus,
    IngestionJobState,
    MembershipContext,
    ResearchRunStatus,
    ResearchStepStatus,
    Role,
    SourceStatus,
    SourceType,
    ToolInvocationStatus,
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
    parser_name: str | None = None
    parser_version: str | None = None
    chunker_name: str | None = None
    chunker_version: str | None = None
    normalized_object_key: str | None = None
    normalized_digest_sha256: str | None = None
    chunk_count: int = 0
    character_count: int = 0
    token_count: int = 0
    embedding_set_id: uuid.UUID | None = None
    embedding_count: int = 0
    safe_metadata: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ChunkRecord:
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
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ChunkDraftRecord:
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


@dataclass(frozen=True, slots=True)
class ChunkEmbeddingDraftRecord:
    chunk_ordinal: int
    vector: list[float]
    token_count: int


@dataclass(frozen=True, slots=True)
class ChunkEmbeddingWriteRecord:
    chunk_id: uuid.UUID
    document_version_id: uuid.UUID
    vector: list[float]
    token_count: int


@dataclass(frozen=True, slots=True)
class MissingEmbeddingChunkRecord:
    chunk_id: uuid.UUID
    document_version_id: uuid.UUID
    ordinal: int
    text: str


@dataclass(frozen=True, slots=True)
class EmbeddingSetRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    provider: str
    model: str
    model_version: str
    dimension: int
    normalized: bool
    config: dict[str, object]
    status: EmbeddingSetStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ChunkEmbeddingRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    chunk_id: uuid.UUID
    document_version_id: uuid.UUID
    embedding_set_id: uuid.UUID
    status: ChunkEmbeddingStatus
    token_count: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SearchFilter:
    source_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class SearchCandidate:
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
    text: str
    distance: float
    score: float
    retrieval_stage: Literal["semantic", "lexical", "hybrid"]
    semantic_score: float | None = None
    lexical_score: float | None = None
    rrf_score: float | None = None
    semantic_rank: int | None = None
    lexical_rank: int | None = None
    embedding_set_id: uuid.UUID | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_model_version: str | None = None
    retrieval_provenance: dict[str, object] | None = None


SemanticSearchFilter = SearchFilter
SemanticSearchCandidate = SearchCandidate


@dataclass(frozen=True, slots=True)
class EmbeddingCoverageRecord:
    workspace_id: uuid.UUID
    embedding_set_id: uuid.UUID
    total_ready_chunks: int
    embedded_ready_chunks: int


@dataclass(frozen=True, slots=True)
class EmbeddingBackfillResult:
    embedding_set_id: uuid.UUID
    missing_before: int
    embedded_count: int
    missing_after: int


@dataclass(frozen=True, slots=True)
class AnswerEvidenceDraft:
    candidate: SearchCandidate
    rank: int
    context_text: str


@dataclass(frozen=True, slots=True)
class CitationDraft:
    marker: str
    evidence_rank: int
    quote: str
    answer_start_char: int
    answer_end_char: int


@dataclass(frozen=True, slots=True)
class ValidatedCitationRecord:
    id: uuid.UUID
    marker: str
    evidence_rank: int
    answer_evidence_id: uuid.UUID
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    quote: str
    evidence_start_char: int
    evidence_end_char: int
    answer_start_char: int
    answer_end_char: int
    status: CitationValidationStatus


@dataclass(frozen=True, slots=True)
class AnswerEvidenceRecord:
    id: uuid.UUID
    rank: int
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    source_id: uuid.UUID
    document_title: str
    retrieval_stage: str
    retrieval_score: float
    semantic_score: float | None
    lexical_score: float | None
    rrf_score: float | None
    quote: str
    start_char: int
    end_char: int
    retrieval_provenance: dict[str, object]


@dataclass(frozen=True, slots=True)
class AnswerRunRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    created_by_user_id: uuid.UUID
    status: AnswerRunStatus
    query: str
    answer_text: str
    retrieval_mode: str
    retrieval_config_version: str
    generation_provider: str
    generation_model: str
    generation_model_version: str
    prompt_version: str
    grounding_status: str
    warnings: list[str]
    input_tokens: int
    output_tokens: int
    total_cost_usd: float
    latency_ms: int
    evidence: list[AnswerEvidenceRecord]
    citations: list[ValidatedCitationRecord]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EvaluationDatasetRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    status: EvaluationDatasetStatus
    latest_version_id: uuid.UUID | None
    latest_version_number: int | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EvaluationCaseDraft:
    query: str
    retrieval_mode: Literal["semantic", "lexical", "hybrid"]
    retrieval_config_version: str
    top_k: int
    relevant_chunk_ids: list[uuid.UUID]
    expected_answer_substrings: list[str]
    expected_citation_quotes: list[str]
    slices: list[str]
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class EvaluationCaseRecord(EvaluationCaseDraft):
    id: uuid.UUID
    workspace_id: uuid.UUID
    dataset_version_id: uuid.UUID
    ordinal: int


@dataclass(frozen=True, slots=True)
class EvaluationDatasetVersionRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    dataset_id: uuid.UUID
    version_number: int
    description: str | None
    case_count: int
    content_digest: str
    config: dict[str, object]
    cases: list[EvaluationCaseRecord]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EvaluationResultRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    evaluation_run_id: uuid.UUID
    evaluation_case_id: uuid.UUID
    status: EvaluationResultStatus
    metrics: dict[str, object]
    retrieved_chunk_ids: list[uuid.UUID]
    answer_run_id: uuid.UUID | None
    error_code: str | None
    error_message: str | None
    latency_ms: int
    total_cost_usd: float
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EvaluationRunRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    dataset_version_id: uuid.UUID
    created_by_user_id: uuid.UUID
    status: EvaluationRunStatus
    run_name: str
    evaluation_config: dict[str, object]
    metric_versions: dict[str, str]
    code_revision: str
    aggregate_metrics: dict[str, object]
    slice_metrics: dict[str, object]
    failure_summary: dict[str, object]
    total_cost_usd: float
    latency_ms: int
    started_at: datetime
    completed_at: datetime | None
    results: list[EvaluationResultRecord]


@dataclass(frozen=True, slots=True)
class EvaluationBaselineRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    dataset_id: uuid.UUID
    dataset_version_id: uuid.UUID
    evaluation_run_id: uuid.UUID
    approved_by_user_id: uuid.UUID
    notes: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ResearchBudget:
    max_steps: int
    max_tool_calls: int
    max_input_tokens: int
    max_output_tokens: int
    max_cost_usd: float
    max_wall_time_ms: int


@dataclass(frozen=True, slots=True)
class ResearchStepDraft:
    ordinal: int
    node_name: str
    status: ResearchStepStatus
    input_summary: dict[str, object]
    output_summary: dict[str, object]
    error_code: str | None = None
    error_message: str | None = None
    latency_ms: int = 0


@dataclass(frozen=True, slots=True)
class ToolInvocationDraft:
    step_ordinal: int
    tool_name: str
    status: ToolInvocationStatus
    input_summary: dict[str, object]
    output_summary: dict[str, object]
    idempotency_key: str
    latency_ms: int = 0
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ResearchApprovalRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    research_run_id: uuid.UUID
    requested_by_user_id: uuid.UUID
    approved_by_user_id: uuid.UUID | None
    status: ApprovalStatus
    approval_type: str
    reason: str
    approval_payload: dict[str, object]
    version: int
    created_at: datetime
    decided_at: datetime | None


@dataclass(frozen=True, slots=True)
class ResearchStepRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    research_run_id: uuid.UUID
    ordinal: int
    node_name: str
    status: ResearchStepStatus
    input_summary: dict[str, object]
    output_summary: dict[str, object]
    error_code: str | None
    error_message: str | None
    latency_ms: int
    started_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ToolInvocationRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    research_run_id: uuid.UUID
    research_step_id: uuid.UUID
    tool_name: str
    status: ToolInvocationStatus
    input_summary: dict[str, object]
    output_summary: dict[str, object]
    idempotency_key: str
    latency_ms: int
    error_code: str | None
    error_message: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CheckpointRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    research_run_id: uuid.UUID
    schema_version: str
    state: dict[str, object]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ResearchRunRecord:
    id: uuid.UUID
    workspace_id: uuid.UUID
    created_by_user_id: uuid.UUID
    purpose: str
    question: str
    status: ResearchRunStatus
    graph_version: str
    config_version: str
    model_versions: dict[str, str]
    input_hash: str
    budget: dict[str, object]
    usage: dict[str, object]
    report_text: str | None
    evidence: list[dict[str, object]]
    warnings: list[str]
    terminal_reason: str | None
    cancellation_requested: bool
    version: int
    total_cost_usd: float
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    steps: list[ResearchStepRecord]
    tool_invocations: list[ToolInvocationRecord]
    approvals: list[ResearchApprovalRecord]
    checkpoints: list[CheckpointRecord]


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

    async def list_chunks(
        self,
        actor: Actor,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> list[ChunkRecord]: ...

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
    ) -> EmbeddingSetRecord: ...

    async def semantic_search(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        embedding_set_id: uuid.UUID,
        query_vector: list[float],
        top_k: int,
        filters: SearchFilter,
    ) -> list[SearchCandidate]: ...

    async def lexical_search(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        query: str,
        top_k: int,
        filters: SearchFilter,
        language: str,
    ) -> list[SearchCandidate]: ...

    async def embedding_coverage(
        self, workspace_id: uuid.UUID, embedding_set_id: uuid.UUID
    ) -> EmbeddingCoverageRecord: ...

    async def list_missing_embedding_chunks(
        self, workspace_id: uuid.UUID, embedding_set_id: uuid.UUID, *, limit: int
    ) -> list[MissingEmbeddingChunkRecord]: ...

    async def write_chunk_embeddings(
        self,
        workspace_id: uuid.UUID,
        embedding_set_id: uuid.UUID,
        embeddings: list[ChunkEmbeddingWriteRecord],
    ) -> int: ...

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
    ) -> AnswerRunRecord: ...

    async def get_answer_run(
        self,
        *,
        workspace_id: uuid.UUID,
        answer_run_id: uuid.UUID,
    ) -> AnswerRunRecord | None: ...

    async def validate_ready_chunk_ids(
        self, workspace_id: uuid.UUID, chunk_ids: list[uuid.UUID]
    ) -> set[uuid.UUID]: ...

    async def create_evaluation_dataset(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        name: str,
        description: str | None,
    ) -> EvaluationDatasetRecord: ...

    async def list_evaluation_datasets(
        self, workspace_id: uuid.UUID
    ) -> list[EvaluationDatasetRecord]: ...

    async def get_evaluation_dataset(
        self, workspace_id: uuid.UUID, dataset_id: uuid.UUID
    ) -> EvaluationDatasetRecord | None: ...

    async def create_evaluation_dataset_version(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        dataset_id: uuid.UUID,
        description: str | None,
        config: dict[str, object],
        content_digest: str,
        cases: list[EvaluationCaseDraft],
    ) -> EvaluationDatasetVersionRecord: ...

    async def get_evaluation_dataset_version(
        self, workspace_id: uuid.UUID, dataset_version_id: uuid.UUID
    ) -> EvaluationDatasetVersionRecord | None: ...

    async def create_evaluation_run(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        dataset_version_id: uuid.UUID,
        run_name: str,
        evaluation_config: dict[str, object],
        metric_versions: dict[str, str],
        code_revision: str,
    ) -> EvaluationRunRecord: ...

    async def complete_evaluation_run(
        self,
        *,
        workspace_id: uuid.UUID,
        evaluation_run_id: uuid.UUID,
        status: EvaluationRunStatus,
        aggregate_metrics: dict[str, object],
        slice_metrics: dict[str, object],
        failure_summary: dict[str, object],
        total_cost_usd: float,
        latency_ms: int,
        results: list[EvaluationResultRecord],
    ) -> EvaluationRunRecord: ...

    async def list_evaluation_runs(
        self, workspace_id: uuid.UUID, *, limit: int
    ) -> list[EvaluationRunRecord]: ...

    async def get_evaluation_run(
        self, workspace_id: uuid.UUID, evaluation_run_id: uuid.UUID
    ) -> EvaluationRunRecord | None: ...

    async def approve_evaluation_baseline(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        evaluation_run_id: uuid.UUID,
        notes: str | None,
    ) -> EvaluationBaselineRecord: ...


class ResearchStore(Protocol):
    async def create_research_run(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        purpose: str,
        question: str,
        graph_version: str,
        config_version: str,
        model_versions: dict[str, str],
        input_hash: str,
        budget: dict[str, object],
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[ResearchRunRecord, bool]: ...

    async def get_research_run(
        self, workspace_id: uuid.UUID, research_run_id: uuid.UUID
    ) -> ResearchRunRecord | None: ...

    async def list_research_runs(
        self, workspace_id: uuid.UUID, *, limit: int
    ) -> list[ResearchRunRecord]: ...

    async def append_research_progress(
        self,
        *,
        workspace_id: uuid.UUID,
        research_run_id: uuid.UUID,
        expected_version: int,
        status: ResearchRunStatus,
        usage: dict[str, object],
        report_text: str | None,
        evidence: list[dict[str, object]],
        warnings: list[str],
        terminal_reason: str | None,
        steps: list[ResearchStepDraft],
        tool_invocations: list[ToolInvocationDraft],
        checkpoint: dict[str, object],
        approval: ResearchApprovalRecord | None = None,
    ) -> ResearchRunRecord: ...

    async def request_approval(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        research_run_id: uuid.UUID,
        expected_run_version: int,
        approval_type: str,
        reason: str,
        approval_payload: dict[str, object],
    ) -> ResearchRunRecord: ...

    async def decide_approval(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        research_run_id: uuid.UUID,
        approval_id: uuid.UUID,
        expected_version: int,
        approved: bool,
    ) -> ResearchRunRecord: ...

    async def cancel_research_run(
        self,
        *,
        workspace_id: uuid.UUID,
        research_run_id: uuid.UUID,
        expected_version: int,
    ) -> ResearchRunRecord: ...


class Transaction(Protocol):
    workspaces: WorkspaceStore
    documents: DocumentStore
    research: ResearchStore

    async def __aenter__(self) -> Transaction: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class TransactionFactory(Protocol):
    def __call__(self) -> Transaction: ...
