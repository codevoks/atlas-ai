from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Permission(StrEnum):
    WORKSPACE_READ = "workspace:read"
    WORKSPACE_UPDATE = "workspace:update"
    MEMBER_LIST = "member:list"
    MEMBER_ADD = "member:add"
    MEMBER_UPDATE = "member:update"
    MEMBER_REMOVE = "member:remove"
    AUDIT_READ = "audit:read"


@dataclass(frozen=True, slots=True)
class IdentityClaims:
    issuer: str
    subject: str
    email: str
    display_name: str


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: uuid.UUID
    issuer: str
    subject: str
    email: str
    display_name: str


@dataclass(frozen=True, slots=True)
class MembershipContext:
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: Role
    status: MembershipStatus
