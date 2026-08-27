from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from atlas_api.application.services import DocumentService, WorkspaceService
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


ActorDependency = Annotated[Actor, Depends(get_current_actor)]
WorkspaceServiceDependency = Annotated[WorkspaceService, Depends(get_workspace_service)]
DocumentServiceDependency = Annotated[DocumentService, Depends(get_document_service)]
