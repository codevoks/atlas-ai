from __future__ import annotations

import uuid

import pytest

from atlas_api.domain.errors import ForbiddenError
from atlas_api.domain.models import MembershipContext, MembershipStatus, Permission, Role
from atlas_api.domain.policy import can_manage_role, require_permission


def context(role: Role, status: MembershipStatus = MembershipStatus.ACTIVE) -> MembershipContext:
    return MembershipContext(
        workspace_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        role=role,
        status=status,
    )


@pytest.mark.parametrize(
    ("role", "permission", "allowed"),
    [
        (Role.OWNER, Permission.MEMBER_REMOVE, True),
        (Role.ADMIN, Permission.WORKSPACE_UPDATE, True),
        (Role.ADMIN, Permission.MEMBER_ADD, True),
        (Role.MEMBER, Permission.MEMBER_LIST, True),
        (Role.MEMBER, Permission.WORKSPACE_UPDATE, False),
        (Role.VIEWER, Permission.WORKSPACE_READ, True),
        (Role.VIEWER, Permission.MEMBER_LIST, False),
    ],
)
def test_role_permission_matrix(role: Role, permission: Permission, allowed: bool) -> None:
    if allowed:
        require_permission(context(role), permission)
    else:
        with pytest.raises(ForbiddenError):
            require_permission(context(role), permission)


def test_suspended_membership_cannot_use_permissions() -> None:
    with pytest.raises(ForbiddenError):
        require_permission(
            context(Role.OWNER, MembershipStatus.SUSPENDED),
            Permission.WORKSPACE_UPDATE,
        )


def test_admin_cannot_manage_owner_or_create_owner() -> None:
    assert can_manage_role(Role.ADMIN, Role.MEMBER, Role.VIEWER)
    assert not can_manage_role(Role.ADMIN, Role.OWNER, Role.ADMIN)
    assert not can_manage_role(Role.ADMIN, Role.MEMBER, Role.OWNER)
    assert not can_manage_role(Role.MEMBER, Role.VIEWER, Role.MEMBER)
