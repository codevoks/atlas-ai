from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from atlas_api.application.services import (
    AnswerService,
    DocumentService,
    EvaluationService,
    SemanticSearchService,
    WorkspaceService,
)
from atlas_api.domain.errors import UnauthenticatedError
from atlas_api.domain.models import Actor

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_actor(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Actor:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthenticatedError()
    claims = await request.app.state.identity_verifier.verify(credentials.credentials)
    actor = await request.app.state.identity_repository.resolve(claims)
    return cast(Actor, actor)


def get_workspace_service(request: Request) -> WorkspaceService:
    return cast(WorkspaceService, request.app.state.workspace_service)


def get_document_service(request: Request) -> DocumentService:
    return cast(DocumentService, request.app.state.document_service)


def get_semantic_search_service(request: Request) -> SemanticSearchService:
    return cast(SemanticSearchService, request.app.state.semantic_search_service)


def get_answer_service(request: Request) -> AnswerService:
    return cast(AnswerService, request.app.state.answer_service)


def get_evaluation_service(request: Request) -> EvaluationService:
    return cast(EvaluationService, request.app.state.evaluation_service)


ActorDependency = Annotated[Actor, Depends(get_current_actor)]
WorkspaceServiceDependency = Annotated[WorkspaceService, Depends(get_workspace_service)]
DocumentServiceDependency = Annotated[DocumentService, Depends(get_document_service)]
SemanticSearchServiceDependency = Annotated[
    SemanticSearchService, Depends(get_semantic_search_service)
]
AnswerServiceDependency = Annotated[AnswerService, Depends(get_answer_service)]
EvaluationServiceDependency = Annotated[EvaluationService, Depends(get_evaluation_service)]
