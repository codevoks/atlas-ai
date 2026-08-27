from __future__ import annotations

import hashlib
import json
import uuid
from types import TracebackType

from sqlalchemy import Select, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from atlas_api.application.ports import MemberRecord, Transaction, WorkspaceRecord, WorkspaceStore
from atlas_api.domain.errors import ConflictError, ResourceNotFoundError
from atlas_api.domain.models import (
    Actor,
    IdentityClaims,
    MembershipContext,
    MembershipStatus,
    Role,
)
from atlas_api.infrastructure.models import (
    AuditEventModel,
    IdempotencyRecordModel,
    MembershipModel,
    UserModel,
    WorkspaceModel,
)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _advisory_lock_id(value: str) -> int:
    unsigned = int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:8], "big")
    return unsigned if unsigned < 2**63 else unsigned - 2**64


class IdentityRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def resolve(self, claims: IdentityClaims) -> Actor:
        normalized_email = claims.email.strip().lower()
        async with self._sessions() as session, session.begin():
            existing = await session.scalar(
                select(UserModel).where(
                    UserModel.issuer == claims.issuer,
                    UserModel.subject == claims.subject,
                )
            )
            if existing is None:
                existing = UserModel(
                    issuer=claims.issuer,
                    subject=claims.subject,
                    email=normalized_email,
                    display_name=claims.display_name.strip(),
                )
                session.add(existing)
                try:
                    await session.flush()
                except IntegrityError as error:
                    raise ConflictError(
                        "The identity email is already associated with another subject."
                    ) from error
            else:
                existing.email = normalized_email
                existing.display_name = claims.display_name.strip()
            await session.flush()
            return Actor(
                user_id=existing.id,
                issuer=existing.issuer,
                subject=existing.subject,
                email=existing.email,
                display_name=existing.display_name,
            )


class SqlAlchemyWorkspaceStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def membership_context(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, *, lock: bool = False
    ) -> MembershipContext | None:
        if lock:
            await self._session.execute(
                select(WorkspaceModel.id).where(WorkspaceModel.id == workspace_id).with_for_update()
            )
        statement: Select[tuple[MembershipModel]] = select(MembershipModel).where(
            MembershipModel.workspace_id == workspace_id,
            MembershipModel.user_id == user_id,
        )
        membership = await self._session.scalar(statement)
        if membership is None:
            return None
        return MembershipContext(
            workspace_id=membership.workspace_id,
            user_id=membership.user_id,
            role=Role(membership.role),
            status=MembershipStatus(membership.status),
        )

    async def list_workspaces(self, user_id: uuid.UUID) -> list[WorkspaceRecord]:
        rows = (
            await self._session.execute(
                select(WorkspaceModel, MembershipModel.role)
                .join(
                    MembershipModel,
                    (MembershipModel.workspace_id == WorkspaceModel.id)
                    & (MembershipModel.user_id == user_id),
                )
                .where(MembershipModel.status == MembershipStatus.ACTIVE.value)
                .order_by(WorkspaceModel.created_at.asc(), WorkspaceModel.id.asc())
            )
        ).all()
        return [
            WorkspaceRecord(
                id=workspace.id, name=workspace.name, version=workspace.version, role=Role(role)
            )
            for workspace, role in rows
        ]

    async def get_workspace(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkspaceRecord | None:
        row = (
            await self._session.execute(
                select(WorkspaceModel, MembershipModel.role)
                .join(
                    MembershipModel,
                    (MembershipModel.workspace_id == WorkspaceModel.id)
                    & (MembershipModel.user_id == user_id),
                )
                .where(
                    WorkspaceModel.id == workspace_id,
                    MembershipModel.status == MembershipStatus.ACTIVE.value,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        workspace, role = row
        return WorkspaceRecord(
            id=workspace.id, name=workspace.name, version=workspace.version, role=Role(role)
        )

    async def create_workspace(
        self, actor: Actor, name: str, idempotency_key: str, request_id: str
    ) -> tuple[WorkspaceRecord, bool]:
        operation = "workspace:create"
        key_hash = _sha256(idempotency_key)
        request_hash = _sha256(json.dumps({"name": name}, sort_keys=True))
        lock_id = _advisory_lock_id(f"{actor.user_id}:{operation}:{key_hash}")
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id}
        )

        prior = await self._session.scalar(
            select(IdempotencyRecordModel).where(
                IdempotencyRecordModel.actor_user_id == actor.user_id,
                IdempotencyRecordModel.operation == operation,
                IdempotencyRecordModel.key_hash == key_hash,
            )
        )
        if prior is not None:
            if prior.request_hash != request_hash:
                raise ConflictError("The idempotency key was already used for a different request.")
            body = prior.response_body
            return (
                WorkspaceRecord(
                    id=uuid.UUID(body["id"]),
                    name=str(body["name"]),
                    version=int(body["version"]),
                    role=Role(str(body["role"])),
                ),
                True,
            )

        workspace = WorkspaceModel(name=name)
        self._session.add(workspace)
        await self._session.flush()
        membership = MembershipModel(
            workspace_id=workspace.id,
            user_id=actor.user_id,
            role=Role.OWNER.value,
            status=MembershipStatus.ACTIVE.value,
        )
        self._session.add(membership)
        await self._audit(
            workspace.id,
            actor,
            "workspace.created",
            "workspace",
            workspace.id,
            request_id,
            {"name": name},
        )
        record = WorkspaceRecord(
            id=workspace.id, name=workspace.name, version=workspace.version, role=Role.OWNER
        )
        self._session.add(
            IdempotencyRecordModel(
                actor_user_id=actor.user_id,
                operation=operation,
                key_hash=key_hash,
                request_hash=request_hash,
                response_status=201,
                response_body={
                    "id": str(record.id),
                    "name": record.name,
                    "version": record.version,
                    "role": record.role.value,
                },
            )
        )
        return record, False

    async def rename_workspace(
        self,
        workspace_id: uuid.UUID,
        name: str,
        expected_version: int,
        actor: Actor,
        actor_role: Role,
        request_id: str,
    ) -> WorkspaceRecord:
        row = (
            await self._session.execute(
                update(WorkspaceModel)
                .where(
                    WorkspaceModel.id == workspace_id, WorkspaceModel.version == expected_version
                )
                .values(name=name, version=WorkspaceModel.version + 1)
                .returning(WorkspaceModel.id, WorkspaceModel.name, WorkspaceModel.version)
            )
        ).one_or_none()
        if row is None:
            exists = await self._session.scalar(
                select(WorkspaceModel.id).where(WorkspaceModel.id == workspace_id)
            )
            if exists is None:
                raise ResourceNotFoundError()
            raise ConflictError("The workspace changed; refresh and retry.")
        await self._audit(
            workspace_id,
            actor,
            "workspace.renamed",
            "workspace",
            workspace_id,
            request_id,
            {"name": name},
        )
        return WorkspaceRecord(id=row.id, name=row.name, version=row.version, role=actor_role)

    async def list_members(self, workspace_id: uuid.UUID) -> list[MemberRecord]:
        rows = (
            await self._session.execute(
                select(MembershipModel, UserModel)
                .join(UserModel, UserModel.id == MembershipModel.user_id)
                .where(
                    MembershipModel.workspace_id == workspace_id,
                    MembershipModel.status == MembershipStatus.ACTIVE.value,
                )
                .order_by(UserModel.email.asc())
            )
        ).all()
        return [self._member_record(membership, user) for membership, user in rows]

    async def add_member(
        self, workspace_id: uuid.UUID, email: str, role: Role, actor: Actor, request_id: str
    ) -> MemberRecord:
        user = await self._session.scalar(
            select(UserModel).where(
                UserModel.issuer == actor.issuer,
                func.lower(UserModel.email) == email.strip().lower(),
            )
        )
        if user is None:
            raise ResourceNotFoundError(
                "The user must sign in once before membership can be added."
            )
        existing = await self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.workspace_id == workspace_id,
                MembershipModel.user_id == user.id,
            )
        )
        if existing is not None:
            raise ConflictError("The user is already a workspace member.")
        membership = MembershipModel(
            workspace_id=workspace_id,
            user_id=user.id,
            role=role.value,
            status=MembershipStatus.ACTIVE.value,
        )
        self._session.add(membership)
        await self._session.flush()
        await self._audit(
            workspace_id,
            actor,
            "membership.added",
            "user",
            user.id,
            request_id,
            {"role": role.value},
        )
        return self._member_record(membership, user)

    async def update_member_role(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: Role,
        expected_version: int,
        actor: Actor,
        request_id: str,
    ) -> MemberRecord:
        membership = await self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.workspace_id == workspace_id,
                MembershipModel.user_id == user_id,
            )
        )
        if membership is None:
            raise ResourceNotFoundError()
        if membership.version != expected_version:
            raise ConflictError("The membership changed; refresh and retry.")
        if membership.role == Role.OWNER.value and role is not Role.OWNER:
            await self._require_another_owner(workspace_id, user_id)
        membership.role = role.value
        membership.version += 1
        user = await self._session.get(UserModel, user_id)
        if user is None:
            raise ResourceNotFoundError()
        await self._audit(
            workspace_id,
            actor,
            "membership.role_changed",
            "user",
            user_id,
            request_id,
            {"role": role.value},
        )
        return self._member_record(membership, user)

    async def remove_member(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, actor: Actor, request_id: str
    ) -> None:
        membership = await self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.workspace_id == workspace_id,
                MembershipModel.user_id == user_id,
            )
        )
        if membership is None:
            raise ResourceNotFoundError()
        if membership.role == Role.OWNER.value:
            await self._require_another_owner(workspace_id, user_id)
        await self._session.delete(membership)
        await self._audit(
            workspace_id, actor, "membership.removed", "user", user_id, request_id, {}
        )

    async def _require_another_owner(
        self, workspace_id: uuid.UUID, excluded_user_id: uuid.UUID
    ) -> None:
        other_owner = await self._session.scalar(
            select(MembershipModel.id).where(
                MembershipModel.workspace_id == workspace_id,
                MembershipModel.user_id != excluded_user_id,
                MembershipModel.role == Role.OWNER.value,
                MembershipModel.status == MembershipStatus.ACTIVE.value,
            )
        )
        if other_owner is None:
            raise ConflictError("A workspace must retain at least one active owner.")

    async def _audit(
        self,
        workspace_id: uuid.UUID,
        actor: Actor,
        action: str,
        target_type: str,
        target_id: uuid.UUID,
        request_id: str,
        safe_metadata: dict[str, str],
    ) -> None:
        self._session.add(
            AuditEventModel(
                workspace_id=workspace_id,
                actor_user_id=actor.user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                request_id=request_id,
                safe_metadata=safe_metadata,
            )
        )

    @staticmethod
    def _member_record(membership: MembershipModel, user: UserModel) -> MemberRecord:
        return MemberRecord(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=Role(membership.role),
            version=membership.version,
        )


class SqlAlchemyTransaction:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self.workspaces: WorkspaceStore

    async def __aenter__(self) -> SqlAlchemyTransaction:
        self._session = self._session_factory()
        await self._session.begin()
        self.workspaces = SqlAlchemyWorkspaceStore(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        try:
            if exc_type is None:
                await self._session.commit()
            else:
                await self._session.rollback()
        finally:
            await self._session.close()


class SqlAlchemyTransactionFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> Transaction:
        return SqlAlchemyTransaction(self._session_factory)
