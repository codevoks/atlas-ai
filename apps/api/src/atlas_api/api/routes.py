from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response, status
from sqlalchemy import text

from atlas_api.api.dependencies import ActorDependency, WorkspaceServiceDependency
from atlas_api.api.schemas import (
    HealthResponse,
    MemberCreate,
    MemberListResponse,
    MemberResponse,
    MemberUpdate,
    MeResponse,
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)
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
