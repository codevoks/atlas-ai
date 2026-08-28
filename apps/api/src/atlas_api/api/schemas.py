from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from atlas_api.application.ports import (
    AnswerEvidenceRecord,
    AnswerRunRecord,
    CheckpointRecord,
    ChunkRecord,
    DocumentRecord,
    DocumentVersionRecord,
    EmbeddingBackfillResult,
    EvaluationBaselineRecord,
    EvaluationCaseDraft,
    EvaluationCaseRecord,
    EvaluationDatasetRecord,
    EvaluationDatasetVersionRecord,
    EvaluationResultRecord,
    EvaluationRunRecord,
    IngestionJobRecord,
    MemberRecord,
    ResearchApprovalRecord,
    ResearchRunRecord,
    ResearchStepRecord,
    SearchCandidate,
    SourceRecord,
    ToolInvocationRecord,
    UploadIntentRecord,
    ValidatedCitationRecord,
    WorkspaceRecord,
)
from atlas_api.domain.models import (
    Actor,
    ApprovalStatus,
    DocumentStatus,
    DocumentVersionStatus,
    IngestionJobState,
    ResearchRunStatus,
    ResearchStepStatus,
    Role,
    SourceStatus,
    SourceType,
    ToolInvocationStatus,
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


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)
    mode: Literal["semantic", "lexical", "hybrid"] = "hybrid"
    retrieval_config_version: Literal[
        "phase5-postgres-fts-rrf-v1", "phase8-multi-query-expansion-v1"
    ] = "phase5-postgres-fts-rrf-v1"
    top_k: int | None = Field(default=None, ge=1, le=20)
    filters: SemanticSearchFilters = Field(default_factory=SemanticSearchFilters)
    debug: bool = False


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)
    retrieval_config_version: Literal[
        "phase5-postgres-fts-rrf-v1", "phase8-multi-query-expansion-v1"
    ] = "phase5-postgres-fts-rrf-v1"
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
    retrieval_stage: Literal["semantic", "lexical", "hybrid"] = "semantic"
    semantic_score: float | None = None
    lexical_score: float | None = None
    rrf_score: float | None = None
    semantic_rank: int | None = None
    lexical_rank: int | None = None
    embedding_set_id: uuid.UUID | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_model_version: str | None = None
    retrieval_provenance: dict[str, object] = Field(default_factory=dict)

    @classmethod
    def from_candidate(cls, candidate: SearchCandidate) -> EvidenceResponse:
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
            retrieval_stage=candidate.retrieval_stage,
            semantic_score=candidate.semantic_score,
            lexical_score=candidate.lexical_score,
            rrf_score=candidate.rrf_score,
            semantic_rank=candidate.semantic_rank,
            lexical_rank=candidate.lexical_rank,
            embedding_set_id=candidate.embedding_set_id,
            embedding_provider=candidate.embedding_provider,
            embedding_model=candidate.embedding_model,
            embedding_model_version=candidate.embedding_model_version,
            retrieval_provenance=candidate.retrieval_provenance or {},
        )


class SearchResponse(BaseModel):
    mode: Literal["semantic", "lexical", "hybrid"]
    retrieval_config_version: str
    items: list[EvidenceResponse]
    trace_id: str
    debug: dict[str, object] | None = None


class AnswerRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)
    retrieval_mode: Literal["semantic", "lexical", "hybrid"] = "hybrid"
    retrieval_config_version: Literal[
        "phase5-postgres-fts-rrf-v1", "phase8-multi-query-expansion-v1"
    ] = "phase5-postgres-fts-rrf-v1"
    top_k: int | None = Field(default=None, ge=1, le=20)
    filters: SemanticSearchFilters = Field(default_factory=SemanticSearchFilters)


class AnswerEvidenceResponse(BaseModel):
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

    @classmethod
    def from_record(cls, record: AnswerEvidenceRecord) -> AnswerEvidenceResponse:
        return cls(
            id=record.id,
            rank=record.rank,
            chunk_id=record.chunk_id,
            document_id=record.document_id,
            document_version_id=record.document_version_id,
            source_id=record.source_id,
            document_title=record.document_title,
            retrieval_stage=record.retrieval_stage,
            retrieval_score=record.retrieval_score,
            semantic_score=record.semantic_score,
            lexical_score=record.lexical_score,
            rrf_score=record.rrf_score,
            quote=record.quote,
            start_char=record.start_char,
            end_char=record.end_char,
            retrieval_provenance=record.retrieval_provenance,
        )


class CitationResponse(BaseModel):
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
    status: str

    @classmethod
    def from_record(cls, record: ValidatedCitationRecord) -> CitationResponse:
        return cls(
            id=record.id,
            marker=record.marker,
            evidence_rank=record.evidence_rank,
            answer_evidence_id=record.answer_evidence_id,
            chunk_id=record.chunk_id,
            document_id=record.document_id,
            document_version_id=record.document_version_id,
            quote=record.quote,
            evidence_start_char=record.evidence_start_char,
            evidence_end_char=record.evidence_end_char,
            answer_start_char=record.answer_start_char,
            answer_end_char=record.answer_end_char,
            status=record.status.value,
        )


class AnswerResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    status: str
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
    evidence: list[AnswerEvidenceResponse]
    citations: list[CitationResponse]
    created_at: str

    @classmethod
    def from_record(cls, record: AnswerRunRecord) -> AnswerResponse:
        return cls(
            id=record.id,
            workspace_id=record.workspace_id,
            status=record.status.value,
            query=record.query,
            answer_text=record.answer_text,
            retrieval_mode=record.retrieval_mode,
            retrieval_config_version=record.retrieval_config_version,
            generation_provider=record.generation_provider,
            generation_model=record.generation_model,
            generation_model_version=record.generation_model_version,
            prompt_version=record.prompt_version,
            grounding_status=record.grounding_status,
            warnings=record.warnings,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            total_cost_usd=record.total_cost_usd,
            latency_ms=record.latency_ms,
            evidence=[AnswerEvidenceResponse.from_record(item) for item in record.evidence],
            citations=[CitationResponse.from_record(item) for item in record.citations],
            created_at=record.created_at.isoformat(),
        )


class EvaluationDatasetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1_000)


class EvaluationDatasetResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    status: str
    latest_version_id: uuid.UUID | None
    latest_version_number: int | None
    created_at: str

    @classmethod
    def from_record(cls, record: EvaluationDatasetRecord) -> EvaluationDatasetResponse:
        return cls(
            id=record.id,
            workspace_id=record.workspace_id,
            name=record.name,
            description=record.description,
            status=record.status.value,
            latest_version_id=record.latest_version_id,
            latest_version_number=record.latest_version_number,
            created_at=record.created_at.isoformat(),
        )


class EvaluationDatasetListResponse(BaseModel):
    items: list[EvaluationDatasetResponse]


class EvaluationCaseCreate(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)
    retrieval_mode: Literal["semantic", "lexical", "hybrid"] = "hybrid"
    retrieval_config_version: Literal[
        "phase5-postgres-fts-rrf-v1", "phase8-multi-query-expansion-v1"
    ] = "phase5-postgres-fts-rrf-v1"
    top_k: int = Field(default=5, ge=1, le=20)
    relevant_chunk_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    expected_answer_substrings: list[str] = Field(default_factory=list, max_length=10)
    expected_citation_quotes: list[str] = Field(default_factory=list, max_length=10)
    slices: list[str] = Field(default_factory=lambda: ["default"], max_length=10)
    metadata: dict[str, object] = Field(default_factory=dict)

    def to_draft(self) -> EvaluationCaseDraft:
        return EvaluationCaseDraft(
            query=self.query,
            retrieval_mode=self.retrieval_mode,
            retrieval_config_version=self.retrieval_config_version,
            top_k=self.top_k,
            relevant_chunk_ids=self.relevant_chunk_ids,
            expected_answer_substrings=self.expected_answer_substrings,
            expected_citation_quotes=self.expected_citation_quotes,
            slices=self.slices,
            metadata=self.metadata,
        )


class EvaluationDatasetVersionCreate(BaseModel):
    description: str | None = Field(default=None, max_length=1_000)
    cases: list[EvaluationCaseCreate] = Field(min_length=1, max_length=50)


class EvaluationCaseResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    dataset_version_id: uuid.UUID
    ordinal: int
    query: str
    retrieval_mode: str
    retrieval_config_version: str
    top_k: int
    relevant_chunk_ids: list[uuid.UUID]
    expected_answer_substrings: list[str]
    expected_citation_quotes: list[str]
    slices: list[str]
    metadata: dict[str, object]

    @classmethod
    def from_record(cls, record: EvaluationCaseRecord) -> EvaluationCaseResponse:
        return cls(
            id=record.id,
            workspace_id=record.workspace_id,
            dataset_version_id=record.dataset_version_id,
            ordinal=record.ordinal,
            query=record.query,
            retrieval_mode=record.retrieval_mode,
            retrieval_config_version=record.retrieval_config_version,
            top_k=record.top_k,
            relevant_chunk_ids=record.relevant_chunk_ids,
            expected_answer_substrings=record.expected_answer_substrings,
            expected_citation_quotes=record.expected_citation_quotes,
            slices=record.slices,
            metadata=record.metadata,
        )


class EvaluationDatasetVersionResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    dataset_id: uuid.UUID
    version_number: int
    description: str | None
    case_count: int
    content_digest: str
    config: dict[str, object]
    cases: list[EvaluationCaseResponse]
    created_at: str

    @classmethod
    def from_record(
        cls, record: EvaluationDatasetVersionRecord
    ) -> EvaluationDatasetVersionResponse:
        return cls(
            id=record.id,
            workspace_id=record.workspace_id,
            dataset_id=record.dataset_id,
            version_number=record.version_number,
            description=record.description,
            case_count=record.case_count,
            content_digest=record.content_digest,
            config=record.config,
            cases=[EvaluationCaseResponse.from_record(item) for item in record.cases],
            created_at=record.created_at.isoformat(),
        )


class EvaluationRunCreate(BaseModel):
    dataset_version_id: uuid.UUID
    run_name: str = Field(min_length=2, max_length=160)
    retrieval_config_version: (
        Literal["phase5-postgres-fts-rrf-v1", "phase8-multi-query-expansion-v1"] | None
    ) = None


class EvaluationResultResponse(BaseModel):
    id: uuid.UUID
    evaluation_case_id: uuid.UUID
    status: str
    metrics: dict[str, object]
    retrieved_chunk_ids: list[uuid.UUID]
    answer_run_id: uuid.UUID | None
    error_code: str | None
    error_message: str | None
    latency_ms: int
    total_cost_usd: float
    created_at: str

    @classmethod
    def from_record(cls, record: EvaluationResultRecord) -> EvaluationResultResponse:
        return cls(
            id=record.id,
            evaluation_case_id=record.evaluation_case_id,
            status=record.status.value,
            metrics=record.metrics,
            retrieved_chunk_ids=record.retrieved_chunk_ids,
            answer_run_id=record.answer_run_id,
            error_code=record.error_code,
            error_message=record.error_message,
            latency_ms=record.latency_ms,
            total_cost_usd=record.total_cost_usd,
            created_at=record.created_at.isoformat(),
        )


class EvaluationRunResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    dataset_version_id: uuid.UUID
    status: str
    run_name: str
    evaluation_config: dict[str, object]
    metric_versions: dict[str, str]
    code_revision: str
    aggregate_metrics: dict[str, object]
    slice_metrics: dict[str, object]
    failure_summary: dict[str, object]
    total_cost_usd: float
    latency_ms: int
    started_at: str
    completed_at: str | None
    results: list[EvaluationResultResponse]

    @classmethod
    def from_record(cls, record: EvaluationRunRecord) -> EvaluationRunResponse:
        return cls(
            id=record.id,
            workspace_id=record.workspace_id,
            dataset_version_id=record.dataset_version_id,
            status=record.status.value,
            run_name=record.run_name,
            evaluation_config=record.evaluation_config,
            metric_versions=record.metric_versions,
            code_revision=record.code_revision,
            aggregate_metrics=record.aggregate_metrics,
            slice_metrics=record.slice_metrics,
            failure_summary=record.failure_summary,
            total_cost_usd=record.total_cost_usd,
            latency_ms=record.latency_ms,
            started_at=record.started_at.isoformat(),
            completed_at=record.completed_at.isoformat() if record.completed_at else None,
            results=[EvaluationResultResponse.from_record(item) for item in record.results],
        )


class EvaluationRunListResponse(BaseModel):
    items: list[EvaluationRunResponse]


class EvaluationBaselineApprove(BaseModel):
    notes: str | None = Field(default=None, max_length=1_000)


class EvaluationBaselineResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    dataset_id: uuid.UUID
    dataset_version_id: uuid.UUID
    evaluation_run_id: uuid.UUID
    approved_by_user_id: uuid.UUID
    notes: str | None
    created_at: str

    @classmethod
    def from_record(cls, record: EvaluationBaselineRecord) -> EvaluationBaselineResponse:
        return cls(
            id=record.id,
            workspace_id=record.workspace_id,
            dataset_id=record.dataset_id,
            dataset_version_id=record.dataset_version_id,
            evaluation_run_id=record.evaluation_run_id,
            approved_by_user_id=record.approved_by_user_id,
            notes=record.notes,
            created_at=record.created_at.isoformat(),
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


class ResearchRunCreate(BaseModel):
    purpose: str = Field(min_length=2, max_length=160)
    question: str = Field(min_length=1, max_length=4000)


class ResearchRunCancel(BaseModel):
    version: int = Field(ge=1)


class ResearchApprovalDecision(BaseModel):
    version: int = Field(ge=1)
    approved: bool


class ResearchStepResponse(BaseModel):
    id: uuid.UUID
    ordinal: int
    node_name: str
    status: ResearchStepStatus
    input_summary: dict[str, object]
    output_summary: dict[str, object]
    error_code: str | None
    error_message: str | None
    latency_ms: int
    started_at: str
    completed_at: str | None

    @classmethod
    def from_record(cls, record: ResearchStepRecord) -> ResearchStepResponse:
        return cls(
            id=record.id,
            ordinal=record.ordinal,
            node_name=record.node_name,
            status=record.status,
            input_summary=record.input_summary,
            output_summary=record.output_summary,
            error_code=record.error_code,
            error_message=record.error_message,
            latency_ms=record.latency_ms,
            started_at=record.started_at.isoformat(),
            completed_at=record.completed_at.isoformat() if record.completed_at else None,
        )


class ToolInvocationResponse(BaseModel):
    id: uuid.UUID
    research_step_id: uuid.UUID
    tool_name: str
    status: ToolInvocationStatus
    input_summary: dict[str, object]
    output_summary: dict[str, object]
    idempotency_key: str
    latency_ms: int
    error_code: str | None
    error_message: str | None
    created_at: str

    @classmethod
    def from_record(cls, record: ToolInvocationRecord) -> ToolInvocationResponse:
        return cls(
            id=record.id,
            research_step_id=record.research_step_id,
            tool_name=record.tool_name,
            status=record.status,
            input_summary=record.input_summary,
            output_summary=record.output_summary,
            idempotency_key=record.idempotency_key,
            latency_ms=record.latency_ms,
            error_code=record.error_code,
            error_message=record.error_message,
            created_at=record.created_at.isoformat(),
        )


class ResearchApprovalResponse(BaseModel):
    id: uuid.UUID
    status: ApprovalStatus
    approval_type: str
    reason: str
    approval_payload: dict[str, object]
    version: int
    created_at: str
    decided_at: str | None

    @classmethod
    def from_record(cls, record: ResearchApprovalRecord) -> ResearchApprovalResponse:
        return cls(
            id=record.id,
            status=record.status,
            approval_type=record.approval_type,
            reason=record.reason,
            approval_payload=record.approval_payload,
            version=record.version,
            created_at=record.created_at.isoformat(),
            decided_at=record.decided_at.isoformat() if record.decided_at else None,
        )


class CheckpointResponse(BaseModel):
    id: uuid.UUID
    schema_version: str
    state_summary: dict[str, object]
    created_at: str

    @classmethod
    def from_record(cls, record: CheckpointRecord) -> CheckpointResponse:
        evidence = record.state.get("evidence")
        planned_questions = record.state.get("planned_questions")
        return cls(
            id=record.id,
            schema_version=record.schema_version,
            state_summary={
                "next_node": record.state.get("next_node"),
                "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
                "planned_question_count": (
                    len(planned_questions) if isinstance(planned_questions, list) else 0
                ),
                "has_report_hash": bool(record.state.get("report_hash")),
            },
            created_at=record.created_at.isoformat(),
        )


class ResearchRunResponse(BaseModel):
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
    started_at: str
    updated_at: str
    completed_at: str | None
    steps: list[ResearchStepResponse]
    tool_invocations: list[ToolInvocationResponse]
    approvals: list[ResearchApprovalResponse]
    checkpoints: list[CheckpointResponse]

    @classmethod
    def from_record(cls, record: ResearchRunRecord) -> ResearchRunResponse:
        return cls(
            id=record.id,
            workspace_id=record.workspace_id,
            created_by_user_id=record.created_by_user_id,
            purpose=record.purpose,
            question=record.question,
            status=record.status,
            graph_version=record.graph_version,
            config_version=record.config_version,
            model_versions=record.model_versions,
            input_hash=record.input_hash,
            budget=record.budget,
            usage=record.usage,
            report_text=record.report_text,
            evidence=record.evidence,
            warnings=record.warnings,
            terminal_reason=record.terminal_reason,
            cancellation_requested=record.cancellation_requested,
            version=record.version,
            total_cost_usd=record.total_cost_usd,
            started_at=record.started_at.isoformat(),
            updated_at=record.updated_at.isoformat(),
            completed_at=record.completed_at.isoformat() if record.completed_at else None,
            steps=[ResearchStepResponse.from_record(item) for item in record.steps],
            tool_invocations=[
                ToolInvocationResponse.from_record(item) for item in record.tool_invocations
            ],
            approvals=[ResearchApprovalResponse.from_record(item) for item in record.approvals],
            checkpoints=[CheckpointResponse.from_record(item) for item in record.checkpoints],
        )


class ResearchRunListResponse(BaseModel):
    items: list[ResearchRunResponse]


class HealthResponse(BaseModel):
    status: str
    service: str
