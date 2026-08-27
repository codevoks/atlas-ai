from __future__ import annotations

import uuid

from atlas_api.application.ports import MemberRecord, TransactionFactory, WorkspaceRecord
from atlas_api.domain.errors import ForbiddenError, ResourceNotFoundError
from atlas_api.domain.models import Actor, Permission, Role
from atlas_api.domain.policy import can_manage_role, require_permission


class WorkspaceService:
    def __init__(self, transaction_factory: TransactionFactory) -> None:
        self._transactions = transaction_factory

    async def list_workspaces(self, actor: Actor) -> list[WorkspaceRecord]:
        async with self._transactions() as tx:
            return await tx.workspaces.list_workspaces(actor.user_id)

    async def get_workspace(self, actor: Actor, workspace_id: uuid.UUID) -> WorkspaceRecord:
        async with self._transactions() as tx:
            record = await tx.workspaces.get_workspace(workspace_id, actor.user_id)
            if record is None:
                raise ResourceNotFoundError()
            return record

    async def create_workspace(
        self, actor: Actor, name: str, idempotency_key: str, request_id: str
    ) -> tuple[WorkspaceRecord, bool]:
        async with self._transactions() as tx:
            return await tx.workspaces.create_workspace(actor, name, idempotency_key, request_id)

    async def rename_workspace(
        self,
        actor: Actor,
        workspace_id: uuid.UUID,
        name: str,
        expected_version: int,
        request_id: str,
    ) -> WorkspaceRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.WORKSPACE_UPDATE)
            return await tx.workspaces.rename_workspace(
                workspace_id, name, expected_version, actor, membership.role, request_id
            )

    async def list_members(self, actor: Actor, workspace_id: uuid.UUID) -> list[MemberRecord]:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.MEMBER_LIST)
            return await tx.workspaces.list_members(workspace_id)

    async def add_member(
        self,
        actor: Actor,
        workspace_id: uuid.UUID,
        email: str,
        role: Role,
        request_id: str,
    ) -> MemberRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.MEMBER_ADD)
            if not can_manage_role(membership.role, Role.VIEWER, role):
                raise ForbiddenError()
            return await tx.workspaces.add_member(workspace_id, email, role, actor, request_id)

    async def update_member_role(
        self,
        actor: Actor,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: Role,
        expected_version: int,
        request_id: str,
    ) -> MemberRecord:
        async with self._transactions() as tx:
            actor_membership = await tx.workspaces.membership_context(
                workspace_id, actor.user_id, lock=True
            )
            target_membership = await tx.workspaces.membership_context(
                workspace_id, user_id, lock=True
            )
            if actor_membership is None or target_membership is None:
                raise ResourceNotFoundError()
            require_permission(actor_membership, Permission.MEMBER_UPDATE)
            if not can_manage_role(actor_membership.role, target_membership.role, role):
                raise ForbiddenError()
            return await tx.workspaces.update_member_role(
                workspace_id, user_id, role, expected_version, actor, request_id
            )

    async def remove_member(
        self, actor: Actor, workspace_id: uuid.UUID, user_id: uuid.UUID, request_id: str
    ) -> None:
        async with self._transactions() as tx:
            actor_membership = await tx.workspaces.membership_context(
                workspace_id, actor.user_id, lock=True
            )
            target_membership = await tx.workspaces.membership_context(
                workspace_id, user_id, lock=True
            )
            if actor_membership is None or target_membership is None:
                raise ResourceNotFoundError()
            require_permission(actor_membership, Permission.MEMBER_REMOVE)
            if not can_manage_role(actor_membership.role, target_membership.role, None):
                raise ForbiddenError()
            await tx.workspaces.remove_member(workspace_id, user_id, actor, request_id)
