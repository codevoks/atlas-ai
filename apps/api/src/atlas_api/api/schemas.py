from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from atlas_api.application.ports import MemberRecord, WorkspaceRecord
from atlas_api.domain.models import Actor, Role


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


class HealthResponse(BaseModel):
    status: str
    service: str
