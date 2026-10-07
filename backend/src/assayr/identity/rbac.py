"""Roles, permissions and scope-aware grants (see vault: 03-Product/RBAC Matrix.md)."""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    PLATFORM_ADMIN = "platform_admin"
    ISMS_MANAGER = "isms_manager"
    CONTROL_OWNER = "control_owner"
    RISK_OWNER = "risk_owner"
    CONTRIBUTOR = "contributor"
    INTERNAL_AUDITOR = "internal_auditor"
    EXTERNAL_AUDITOR = "external_auditor"
    EXECUTIVE = "executive"
    EMPLOYEE = "employee"
    VIEWER = "viewer"


class Perm(StrEnum):
    CONTROLS_READ = "controls:read"
    CONTROLS_WRITE = "controls:write"
    CONTROLS_WRITE_OWN = "controls:write_own"
    USERS_MANAGE = "users:manage"
    AUDIT_LOG_READ = "audit_log:read"
    SETTINGS_MANAGE = "settings:manage"


ROLE_PERMISSIONS: dict[Role, frozenset[Perm]] = {
    Role.PLATFORM_ADMIN: frozenset(
        {Perm.CONTROLS_READ, Perm.USERS_MANAGE, Perm.SETTINGS_MANAGE, Perm.AUDIT_LOG_READ}
    ),
    Role.ISMS_MANAGER: frozenset({Perm.CONTROLS_READ, Perm.CONTROLS_WRITE, Perm.AUDIT_LOG_READ}),
    Role.CONTROL_OWNER: frozenset({Perm.CONTROLS_READ, Perm.CONTROLS_WRITE_OWN}),
    Role.RISK_OWNER: frozenset({Perm.CONTROLS_READ}),
    Role.CONTRIBUTOR: frozenset({Perm.CONTROLS_READ}),
    Role.INTERNAL_AUDITOR: frozenset({Perm.CONTROLS_READ, Perm.AUDIT_LOG_READ}),
    Role.EXTERNAL_AUDITOR: frozenset({Perm.CONTROLS_READ}),
    Role.EXECUTIVE: frozenset({Perm.CONTROLS_READ}),
    Role.EMPLOYEE: frozenset(),
    Role.VIEWER: frozenset({Perm.CONTROLS_READ}),
}


@dataclass(frozen=True)
class Grant:
    all_scopes: bool
    scope_ids: frozenset[uuid.UUID]

    def allows(self, scope_id: uuid.UUID) -> bool:
        return self.all_scopes or scope_id in self.scope_ids

    @property
    def any(self) -> bool:
        return self.all_scopes or bool(self.scope_ids)


def _role(name: str) -> Role | None:
    try:
        return Role(name)
    except ValueError:
        return None


def grant_for(assignments: Iterable[tuple[str, uuid.UUID | None]], perm: Perm) -> Grant:
    all_scopes = False
    scopes: set[uuid.UUID] = set()
    for role_name, scope_id in assignments:
        role = _role(role_name)
        if role is None or perm not in ROLE_PERMISSIONS[role]:
            continue
        if scope_id is None:
            all_scopes = True
        else:
            scopes.add(scope_id)
    return Grant(all_scopes=all_scopes, scope_ids=frozenset(scopes))


def permissions_for(assignments: Iterable[tuple[str, uuid.UUID | None]]) -> list[str]:
    perms: set[str] = set()
    for role_name, _scope in assignments:
        role = _role(role_name)
        if role is not None:
            perms.update(p.value for p in ROLE_PERMISSIONS[role])
    return sorted(perms)
