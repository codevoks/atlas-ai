from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response, status
from sqlalchemy import text

from atlas_api.api.dependencies import (
    ActorDependency,
    AnswerServiceDependency,
    DocumentServiceDependency,
    EvaluationServiceDependency,
    ResearchServiceDependency,
    SecurityServiceDependency,
    SemanticSearchServiceDependency,
    WorkspaceServiceDependency,
)
from atlas_api.api.schemas import (
    AnswerRequest,
    AnswerResponse,
    ChunkListResponse,
    ChunkResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentVersionListResponse,
    DocumentVersionResponse,
    EmbeddingBackfillRequest,
    EmbeddingBackfillResponse,
    EvaluationBaselineApprove,
    EvaluationBaselineResponse,
    EvaluationDatasetCreate,
    EvaluationDatasetListResponse,
    EvaluationDatasetResponse,
    EvaluationDatasetVersionCreate,
    EvaluationDatasetVersionResponse,
    EvaluationRunCreate,
    EvaluationRunListResponse,
    EvaluationRunResponse,
    EvidenceResponse,
    HealthResponse,
    IngestionJobResponse,
    MemberCreate,
    MemberListResponse,
    MemberResponse,
    MemberUpdate,
    MeResponse,
    ResearchApprovalDecision,
    ResearchRunCancel,
    ResearchRunCreate,
    ResearchRunListResponse,
    ResearchRunResponse,
    SearchRequest,
    SearchResponse,
    SecurityEventListResponse,
    SecurityEventResponse,
    SecurityPostureResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SourceCreate,
    SourceListResponse,
    SourceResponse,
    UploadFinalize,
    UploadFinalizeResponse,
    UploadIntentCreate,
    UploadIntentResponse,
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from atlas_api.application.ports import SearchFilter
from atlas_api.domain.errors import DependencyUnavailableError, ValidationError

router = APIRouter()


@router.get("/health/live", response_model=HealthResponse, tags=["health"])
async def liveness() -> HealthResponse:
    return HealthResponse(status="healthy", service="atlas-api")


@router.get("/health/ready", response_model=HealthResponse, tags=["health"])
async def readiness(request: Request) -> HealthResponse:
    try:
        async with request.app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as error:
        raise DependencyUnavailableError("The database is unavailable.") from error
    return HealthResponse(status="ready", service="atlas-api")


@router.get("/v1/me", response_model=MeResponse, tags=["identity"])
async def me(actor: ActorDependency) -> MeResponse:
    return MeResponse.from_actor(actor)


@router.get("/v1/workspaces", response_model=WorkspaceListResponse, tags=["workspaces"])
async def list_workspaces(
    actor: ActorDependency, service: WorkspaceServiceDependency
) -> WorkspaceListResponse:
    records = await service.list_workspaces(actor)
    return WorkspaceListResponse(items=[WorkspaceResponse.from_record(item) for item in records])


@router.post(
    "/v1/workspaces",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["workspaces"],
)
async def create_workspace(
    payload: WorkspaceCreate,
    request: Request,
    response: Response,
    actor: ActorDependency,
    service: WorkspaceServiceDependency,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WorkspaceResponse:
    if idempotency_key is None or not (8 <= len(idempotency_key) <= 128):
        raise ValidationError("Idempotency-Key must contain between 8 and 128 characters.")
    record, replayed = await service.create_workspace(
        actor, payload.name, idempotency_key, request.state.request_id
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    return WorkspaceResponse.from_record(record)


@router.get("/v1/workspaces/{workspace_id}", response_model=WorkspaceResponse, tags=["workspaces"])
async def get_workspace(
    workspace_id: uuid.UUID,
    actor: ActorDependency,
    service: WorkspaceServiceDependency,
) -> WorkspaceResponse:
    return WorkspaceResponse.from_record(await service.get_workspace(actor, workspace_id))


@router.get(
    "/v1/workspaces/{workspace_id}/security/posture",
    response_model=SecurityPostureResponse,
    tags=["security"],
)
async def security_posture(
    workspace_id: uuid.UUID,
    actor: ActorDependency,
    service: SecurityServiceDependency,
) -> SecurityPostureResponse:
    return SecurityPostureResponse.from_record(await service.posture(actor, workspace_id))


@router.get(
    "/v1/workspaces/{workspace_id}/security/events",
    response_model=SecurityEventListResponse,
    tags=["security"],
)
async def list_security_events(
    workspace_id: uuid.UUID,
    actor: ActorDependency,
    service: SecurityServiceDependency,
    limit: int = 25,
) -> SecurityEventListResponse:
    records = await service.list_security_events(actor, workspace_id, limit=limit)
    return SecurityEventListResponse(
        items=[SecurityEventResponse.from_record(item) for item in records]
    )


@router.patch(
    "/v1/workspaces/{workspace_id}", response_model=WorkspaceResponse, tags=["workspaces"]
)
async def rename_workspace(
    workspace_id: uuid.UUID,
    payload: WorkspaceUpdate,
    request: Request,
    actor: ActorDependency,
    service: WorkspaceServiceDependency,
) -> WorkspaceResponse:
    record = await service.rename_workspace(
        actor, workspace_id, payload.name, payload.version, request.state.request_id
    )
    return WorkspaceResponse.from_record(record)


@router.get(
    "/v1/workspaces/{workspace_id}/members",
    response_model=MemberListResponse,
    tags=["memberships"],
)
async def list_members(
    workspace_id: uuid.UUID,
    actor: ActorDependency,
    service: WorkspaceServiceDependency,
) -> MemberListResponse:
    records = await service.list_members(actor, workspace_id)
    return MemberListResponse(items=[MemberResponse.from_record(item) for item in records])


@router.post(
    "/v1/workspaces/{workspace_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["memberships"],
)
async def add_member(
    workspace_id: uuid.UUID,
    payload: MemberCreate,
    request: Request,
    actor: ActorDependency,
    service: WorkspaceServiceDependency,
) -> MemberResponse:
    record = await service.add_member(
        actor, workspace_id, str(payload.email), payload.role, request.state.request_id
    )
    return MemberResponse.from_record(record)


@router.patch(
    "/v1/workspaces/{workspace_id}/members/{user_id}",
    response_model=MemberResponse,
    tags=["memberships"],
)
async def update_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: MemberUpdate,
    request: Request,
    actor: ActorDependency,
    service: WorkspaceServiceDependency,
) -> MemberResponse:
    record = await service.update_member_role(
        actor,
        workspace_id,
        user_id,
        payload.role,
        payload.version,
        request.state.request_id,
    )
    return MemberResponse.from_record(record)


@router.delete(
    "/v1/workspaces/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["memberships"],
)
async def remove_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    actor: ActorDependency,
    service: WorkspaceServiceDependency,
) -> Response:
    await service.remove_member(actor, workspace_id, user_id, request.state.request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/v1/workspaces/{workspace_id}/sources",
    response_model=SourceListResponse,
    tags=["documents"],
)
async def list_sources(
    workspace_id: uuid.UUID,
    actor: ActorDependency,
    service: DocumentServiceDependency,
) -> SourceListResponse:
    records = await service.list_sources(actor, workspace_id)
    return SourceListResponse(items=[SourceResponse.from_record(item) for item in records])


@router.post(
    "/v1/workspaces/{workspace_id}/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["documents"],
)
async def create_source(
    workspace_id: uuid.UUID,
    payload: SourceCreate,
    request: Request,
    actor: ActorDependency,
    service: DocumentServiceDependency,
) -> SourceResponse:
    record = await service.create_source(
        actor, workspace_id, payload.name, request.state.request_id
    )
    return SourceResponse.from_record(record)


@router.post(
    "/v1/workspaces/{workspace_id}/uploads",
    response_model=UploadIntentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["documents"],
)
async def create_upload_intent(
    workspace_id: uuid.UUID,
    payload: UploadIntentCreate,
    request: Request,
    actor: ActorDependency,
    service: DocumentServiceDependency,
) -> UploadIntentResponse:
    base_url = str(request.base_url).rstrip("/")
    record = await service.create_upload_intent(
        actor=actor,
        workspace_id=workspace_id,
        original_filename=payload.original_filename,
        media_type=payload.media_type,
        byte_size=payload.byte_size,
        digest_sha256=payload.digest_sha256,
        base_url=base_url,
        request_id=request.state.request_id,
    )
    return UploadIntentResponse.from_record(record)


@router.put(
    "/v1/uploads/{upload_intent_id}/content",
    response_model=UploadIntentResponse,
    tags=["documents"],
)
async def upload_content(
    upload_intent_id: uuid.UUID,
    request: Request,
    token: str,
    service: DocumentServiceDependency,
) -> UploadIntentResponse:
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    body = await request.body()
    record = await service.receive_upload_content(
        upload_intent_id=upload_intent_id,
        token=token,
        body=body,
        media_type=media_type,
    )
    return UploadIntentResponse.from_record(record)


@router.post(
    "/v1/workspaces/{workspace_id}/uploads/{upload_intent_id}/finalize",
    response_model=UploadFinalizeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["documents"],
)
async def finalize_upload(
    workspace_id: uuid.UUID,
    upload_intent_id: uuid.UUID,
    payload: UploadFinalize,
    request: Request,
    response: Response,
    actor: ActorDependency,
    service: DocumentServiceDependency,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> UploadFinalizeResponse:
    if idempotency_key is None or not (8 <= len(idempotency_key) <= 128):
        raise ValidationError("Idempotency-Key must contain between 8 and 128 characters.")
    document, version, job, replayed = await service.finalize_upload(
        actor=actor,
        workspace_id=workspace_id,
        source_id=payload.source_id,
        upload_intent_id=upload_intent_id,
        title=payload.title,
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    return UploadFinalizeResponse(
        document=DocumentResponse.from_record(document),
        document_version=DocumentVersionResponse.from_record(version),
        ingestion_job=IngestionJobResponse.from_record(job),
    )


@router.get(
    "/v1/workspaces/{workspace_id}/documents",
    response_model=DocumentListResponse,
    tags=["documents"],
)
async def list_documents(
    workspace_id: uuid.UUID,
    actor: ActorDependency,
    service: DocumentServiceDependency,
) -> DocumentListResponse:
    records = await service.list_documents(actor, workspace_id)
    return DocumentListResponse(items=[DocumentResponse.from_record(item) for item in records])


@router.get(
    "/v1/workspaces/{workspace_id}/documents/{document_id}",
    response_model=DocumentResponse,
    tags=["documents"],
)
async def get_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    actor: ActorDependency,
    service: DocumentServiceDependency,
) -> DocumentResponse:
    return DocumentResponse.from_record(
        await service.get_document(actor, workspace_id, document_id)
    )


@router.get(
    "/v1/workspaces/{workspace_id}/documents/{document_id}/versions",
    response_model=DocumentVersionListResponse,
    tags=["documents"],
)
async def list_document_versions(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    actor: ActorDependency,
    service: DocumentServiceDependency,
) -> DocumentVersionListResponse:
    records = await service.list_versions(actor, workspace_id, document_id)
    return DocumentVersionListResponse(
        items=[DocumentVersionResponse.from_record(item) for item in records]
    )


@router.get(
    "/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/chunks",
    response_model=ChunkListResponse,
    tags=["documents"],
)
async def list_document_version_chunks(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    actor: ActorDependency,
    service: DocumentServiceDependency,
) -> ChunkListResponse:
    records = await service.list_chunks(actor, workspace_id, document_id, version_id)
    return ChunkListResponse(items=[ChunkResponse.from_record(item) for item in records])


@router.post(
    "/v1/workspaces/{workspace_id}/search",
    response_model=SearchResponse,
    tags=["search"],
)
async def search(
    workspace_id: uuid.UUID,
    payload: SearchRequest,
    request: Request,
    actor: ActorDependency,
    service: SemanticSearchServiceDependency,
) -> SearchResponse:
    records, debug = await service.search(
        actor=actor,
        workspace_id=workspace_id,
        query=payload.query,
        top_k=payload.top_k,
        filters=SearchFilter(
            source_id=payload.filters.source_id,
            document_id=payload.filters.document_id,
        ),
        mode=payload.mode,
        retrieval_config_version=payload.retrieval_config_version,
    )
    return SearchResponse(
        mode=payload.mode,
        retrieval_config_version=str(debug["retrieval_config_version"]),
        items=[EvidenceResponse.from_candidate(item) for item in records],
        trace_id=request.state.request_id,
        debug=debug if payload.debug else None,
    )


@router.post(
    "/v1/workspaces/{workspace_id}/search/semantic",
    response_model=SemanticSearchResponse,
    tags=["search"],
)
async def semantic_search(
    workspace_id: uuid.UUID,
    payload: SemanticSearchRequest,
    request: Request,
    actor: ActorDependency,
    service: SemanticSearchServiceDependency,
) -> SemanticSearchResponse:
    records, debug = await service.search(
        actor=actor,
        workspace_id=workspace_id,
        query=payload.query,
        top_k=payload.top_k,
        filters=SearchFilter(
            source_id=payload.filters.source_id,
            document_id=payload.filters.document_id,
        ),
        retrieval_config_version=payload.retrieval_config_version,
    )
    return SemanticSearchResponse(
        items=[EvidenceResponse.from_candidate(item) for item in records],
        trace_id=request.state.request_id,
        debug=debug if payload.debug else None,
    )


@router.post(
    "/v1/workspaces/{workspace_id}/answers",
    response_model=AnswerResponse,
    tags=["answers"],
)
async def create_answer(
    workspace_id: uuid.UUID,
    payload: AnswerRequest,
    actor: ActorDependency,
    service: AnswerServiceDependency,
) -> AnswerResponse:
    record = await service.answer(
        actor=actor,
        workspace_id=workspace_id,
        query=payload.query,
        top_k=payload.top_k,
        filters=SearchFilter(
            source_id=payload.filters.source_id,
            document_id=payload.filters.document_id,
        ),
        retrieval_mode=payload.retrieval_mode,
        retrieval_config_version=payload.retrieval_config_version,
    )
    return AnswerResponse.from_record(record)


@router.get(
    "/v1/workspaces/{workspace_id}/answer-runs/{answer_run_id}",
    response_model=AnswerResponse,
    tags=["answers"],
)
async def get_answer_run(
    workspace_id: uuid.UUID,
    answer_run_id: uuid.UUID,
    actor: ActorDependency,
    service: AnswerServiceDependency,
) -> AnswerResponse:
    record = await service.get_answer_run(
        actor=actor,
        workspace_id=workspace_id,
        answer_run_id=answer_run_id,
    )
    return AnswerResponse.from_record(record)


@router.get(
    "/v1/workspaces/{workspace_id}/evaluation-datasets",
    response_model=EvaluationDatasetListResponse,
    tags=["evaluations"],
)
async def list_evaluation_datasets(
    workspace_id: uuid.UUID,
    actor: ActorDependency,
    service: EvaluationServiceDependency,
) -> EvaluationDatasetListResponse:
    records = await service.list_datasets(actor=actor, workspace_id=workspace_id)
    return EvaluationDatasetListResponse(
        items=[EvaluationDatasetResponse.from_record(item) for item in records]
    )


@router.post(
    "/v1/workspaces/{workspace_id}/evaluation-datasets",
    response_model=EvaluationDatasetResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["evaluations"],
)
async def create_evaluation_dataset(
    workspace_id: uuid.UUID,
    payload: EvaluationDatasetCreate,
    actor: ActorDependency,
    service: EvaluationServiceDependency,
) -> EvaluationDatasetResponse:
    record = await service.create_dataset(
        actor=actor,
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
    )
    return EvaluationDatasetResponse.from_record(record)


@router.post(
    "/v1/workspaces/{workspace_id}/evaluation-datasets/{dataset_id}/versions",
    response_model=EvaluationDatasetVersionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["evaluations"],
)
async def create_evaluation_dataset_version(
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
    payload: EvaluationDatasetVersionCreate,
    actor: ActorDependency,
    service: EvaluationServiceDependency,
) -> EvaluationDatasetVersionResponse:
    record = await service.create_dataset_version(
        actor=actor,
        workspace_id=workspace_id,
        dataset_id=dataset_id,
        description=payload.description,
        cases=[case.to_draft() for case in payload.cases],
    )
    return EvaluationDatasetVersionResponse.from_record(record)


@router.get(
    "/v1/workspaces/{workspace_id}/evaluation-dataset-versions/{dataset_version_id}",
    response_model=EvaluationDatasetVersionResponse,
    tags=["evaluations"],
)
async def get_evaluation_dataset_version(
    workspace_id: uuid.UUID,
    dataset_version_id: uuid.UUID,
    actor: ActorDependency,
    service: EvaluationServiceDependency,
) -> EvaluationDatasetVersionResponse:
    record = await service.get_dataset_version(
        actor=actor,
        workspace_id=workspace_id,
        dataset_version_id=dataset_version_id,
    )
    return EvaluationDatasetVersionResponse.from_record(record)


@router.get(
    "/v1/workspaces/{workspace_id}/evaluation-runs",
    response_model=EvaluationRunListResponse,
    tags=["evaluations"],
)
async def list_evaluation_runs(
    workspace_id: uuid.UUID,
    actor: ActorDependency,
    service: EvaluationServiceDependency,
    limit: int = 10,
) -> EvaluationRunListResponse:
    bounded_limit = max(1, min(limit, 50))
    records = await service.list_runs(actor=actor, workspace_id=workspace_id, limit=bounded_limit)
    return EvaluationRunListResponse(
        items=[EvaluationRunResponse.from_record(item) for item in records]
    )


@router.post(
    "/v1/workspaces/{workspace_id}/evaluation-runs",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["evaluations"],
)
async def create_evaluation_run(
    workspace_id: uuid.UUID,
    payload: EvaluationRunCreate,
    actor: ActorDependency,
    service: EvaluationServiceDependency,
) -> EvaluationRunResponse:
    record = await service.run_evaluation(
        actor=actor,
        workspace_id=workspace_id,
        dataset_version_id=payload.dataset_version_id,
        run_name=payload.run_name,
        retrieval_config_version=payload.retrieval_config_version,
    )
    return EvaluationRunResponse.from_record(record)


@router.get(
    "/v1/workspaces/{workspace_id}/evaluation-runs/{evaluation_run_id}",
    response_model=EvaluationRunResponse,
    tags=["evaluations"],
)
async def get_evaluation_run(
    workspace_id: uuid.UUID,
    evaluation_run_id: uuid.UUID,
    actor: ActorDependency,
    service: EvaluationServiceDependency,
) -> EvaluationRunResponse:
    record = await service.get_run(
        actor=actor,
        workspace_id=workspace_id,
        evaluation_run_id=evaluation_run_id,
    )
    return EvaluationRunResponse.from_record(record)


@router.post(
    "/v1/workspaces/{workspace_id}/evaluation-runs/{evaluation_run_id}/baseline",
    response_model=EvaluationBaselineResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["evaluations"],
)
async def approve_evaluation_baseline(
    workspace_id: uuid.UUID,
    evaluation_run_id: uuid.UUID,
    payload: EvaluationBaselineApprove,
    actor: ActorDependency,
    service: EvaluationServiceDependency,
) -> EvaluationBaselineResponse:
    record = await service.approve_baseline(
        actor=actor,
        workspace_id=workspace_id,
        evaluation_run_id=evaluation_run_id,
        notes=payload.notes,
    )
    return EvaluationBaselineResponse.from_record(record)


@router.get(
    "/v1/workspaces/{workspace_id}/research-runs",
    response_model=ResearchRunListResponse,
    tags=["research"],
)
async def list_research_runs(
    workspace_id: uuid.UUID,
    actor: ActorDependency,
    service: ResearchServiceDependency,
    limit: int = 10,
) -> ResearchRunListResponse:
    records = await service.list_research_runs(actor=actor, workspace_id=workspace_id, limit=limit)
    return ResearchRunListResponse(
        items=[ResearchRunResponse.from_record(item) for item in records]
    )


@router.post(
    "/v1/workspaces/{workspace_id}/research-runs",
    response_model=ResearchRunResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["research"],
)
async def create_research_run(
    workspace_id: uuid.UUID,
    payload: ResearchRunCreate,
    response: Response,
    actor: ActorDependency,
    service: ResearchServiceDependency,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ResearchRunResponse:
    if idempotency_key is None:
        raise ValidationError("Idempotency-Key is required.")
    record, replayed = await service.create_research_run(
        actor=actor,
        workspace_id=workspace_id,
        purpose=payload.purpose,
        question=payload.question,
        idempotency_key=idempotency_key,
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    return ResearchRunResponse.from_record(record)


@router.get(
    "/v1/workspaces/{workspace_id}/research-runs/{research_run_id}",
    response_model=ResearchRunResponse,
    tags=["research"],
)
async def get_research_run(
    workspace_id: uuid.UUID,
    research_run_id: uuid.UUID,
    actor: ActorDependency,
    service: ResearchServiceDependency,
) -> ResearchRunResponse:
    return ResearchRunResponse.from_record(
        await service.get_research_run(
            actor=actor, workspace_id=workspace_id, run_id=research_run_id
        )
    )


@router.post(
    "/v1/workspaces/{workspace_id}/research-runs/{research_run_id}/resume",
    response_model=ResearchRunResponse,
    tags=["research"],
)
async def resume_research_run(
    workspace_id: uuid.UUID,
    research_run_id: uuid.UUID,
    actor: ActorDependency,
    service: ResearchServiceDependency,
) -> ResearchRunResponse:
    return ResearchRunResponse.from_record(
        await service.resume_research_run(
            actor=actor, workspace_id=workspace_id, run_id=research_run_id
        )
    )


@router.post(
    "/v1/workspaces/{workspace_id}/research-runs/{research_run_id}/cancel",
    response_model=ResearchRunResponse,
    tags=["research"],
)
async def cancel_research_run(
    workspace_id: uuid.UUID,
    research_run_id: uuid.UUID,
    payload: ResearchRunCancel,
    actor: ActorDependency,
    service: ResearchServiceDependency,
) -> ResearchRunResponse:
    return ResearchRunResponse.from_record(
        await service.cancel_research_run(
            actor=actor,
            workspace_id=workspace_id,
            run_id=research_run_id,
            expected_version=payload.version,
        )
    )


@router.post(
    "/v1/workspaces/{workspace_id}/research-runs/{research_run_id}/approvals/{approval_id}",
    response_model=ResearchRunResponse,
    tags=["research"],
)
async def decide_research_approval(
    workspace_id: uuid.UUID,
    research_run_id: uuid.UUID,
    approval_id: uuid.UUID,
    payload: ResearchApprovalDecision,
    actor: ActorDependency,
    service: ResearchServiceDependency,
) -> ResearchRunResponse:
    return ResearchRunResponse.from_record(
        await service.decide_approval(
            actor=actor,
            workspace_id=workspace_id,
            run_id=research_run_id,
            approval_id=approval_id,
            expected_version=payload.version,
            approved=payload.approved,
        )
    )


@router.post(
    "/v1/workspaces/{workspace_id}/embeddings/backfill",
    response_model=EmbeddingBackfillResponse,
    tags=["search"],
)
async def backfill_embeddings(
    workspace_id: uuid.UUID,
    payload: EmbeddingBackfillRequest,
    actor: ActorDependency,
    service: SemanticSearchServiceDependency,
) -> EmbeddingBackfillResponse:
    result = await service.backfill_missing_embeddings(
        actor=actor,
        workspace_id=workspace_id,
        limit=payload.limit,
    )
    return EmbeddingBackfillResponse.from_result(result)


@router.delete(
    "/v1/workspaces/{workspace_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["documents"],
)
async def delete_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    actor: ActorDependency,
    service: DocumentServiceDependency,
) -> Response:
    await service.delete_document(actor, workspace_id, document_id, request.state.request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/v1/workspaces/{workspace_id}/ingestion-jobs/{job_id}",
    response_model=IngestionJobResponse,
    tags=["documents"],
)
async def get_ingestion_job(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    actor: ActorDependency,
    service: DocumentServiceDependency,
) -> IngestionJobResponse:
    return IngestionJobResponse.from_record(await service.get_job(actor, workspace_id, job_id))


@router.post(
    "/v1/workspaces/{workspace_id}/ingestion-jobs/{job_id}/cancel",
    response_model=IngestionJobResponse,
    tags=["documents"],
)
async def cancel_ingestion_job(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    request: Request,
    actor: ActorDependency,
    service: DocumentServiceDependency,
) -> IngestionJobResponse:
    return IngestionJobResponse.from_record(
        await service.cancel_job(actor, workspace_id, job_id, request.state.request_id)
    )


@router.post(
    "/v1/workspaces/{workspace_id}/ingestion-jobs/{job_id}/retry",
    response_model=IngestionJobResponse,
    tags=["documents"],
)
async def retry_ingestion_job(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    request: Request,
    actor: ActorDependency,
    service: DocumentServiceDependency,
) -> IngestionJobResponse:
    return IngestionJobResponse.from_record(
        await service.retry_job(actor, workspace_id, job_id, request.state.request_id)
    )
