from __future__ import annotations

from atlas_api.domain.errors import ForbiddenError
from atlas_api.domain.models import MembershipContext, MembershipStatus, Permission, Role

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.ADMIN: frozenset(
        {
            Permission.WORKSPACE_READ,
            Permission.WORKSPACE_UPDATE,
            Permission.MEMBER_LIST,
            Permission.MEMBER_ADD,
            Permission.MEMBER_UPDATE,
            Permission.MEMBER_REMOVE,
            Permission.AUDIT_READ,
            Permission.SOURCE_READ,
            Permission.SOURCE_CREATE,
            Permission.DOCUMENT_READ,
            Permission.DOCUMENT_CREATE,
            Permission.DOCUMENT_DELETE,
            Permission.INGESTION_JOB_READ,
            Permission.INGESTION_JOB_MANAGE,
            Permission.RESEARCH_RUN_READ,
            Permission.RESEARCH_RUN_MANAGE,
            Permission.SECURITY_READ,
            Permission.SECURITY_MANAGE,
        }
    ),
    Role.MEMBER: frozenset(
        {
            Permission.WORKSPACE_READ,
            Permission.MEMBER_LIST,
            Permission.SOURCE_READ,
            Permission.SOURCE_CREATE,
            Permission.DOCUMENT_READ,
            Permission.DOCUMENT_CREATE,
            Permission.DOCUMENT_DELETE,
            Permission.INGESTION_JOB_READ,
            Permission.RESEARCH_RUN_READ,
            Permission.RESEARCH_RUN_MANAGE,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Permission.WORKSPACE_READ,
            Permission.SOURCE_READ,
            Permission.DOCUMENT_READ,
            Permission.INGESTION_JOB_READ,
            Permission.RESEARCH_RUN_READ,
        }
    ),
}


def require_permission(context: MembershipContext | None, permission: Permission) -> None:
    if context is None or context.status is not MembershipStatus.ACTIVE:
        raise ForbiddenError()
    if permission not in ROLE_PERMISSIONS[context.role]:
        raise ForbiddenError()


def can_manage_role(actor_role: Role, target_role: Role, desired_role: Role | None) -> bool:
    if actor_role is Role.OWNER:
        return True
    if actor_role is not Role.ADMIN:
        return False
    if target_role is Role.OWNER or desired_role is Role.OWNER:
        return False
    return True
