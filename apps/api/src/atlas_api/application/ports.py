from __future__ import annotations

import uuid
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol

from atlas_api.domain.models import Actor, MembershipContext, Role


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


class Transaction(Protocol):
    workspaces: WorkspaceStore

    async def __aenter__(self) -> Transaction: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class TransactionFactory(Protocol):
    def __call__(self) -> Transaction: ...
