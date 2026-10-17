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
    EVIDENCE_REVIEW = "evidence:review"
    RISKS_READ = "risks:read"
    RISKS_WRITE = "risks:write"
    RISKS_WRITE_OWN = "risks:write_own"
    RISKS_ACCEPT_MEDIUM_OWN = "risks:accept_medium_own"
    RISKS_ACCEPT_HIGH = "risks:accept_high"
    RISKS_ACCEPT_CRITICAL = "risks:accept_critical"
    ASSETS_READ = "assets:read"
    ASSETS_WRITE = "assets:write"
    ASSETS_WRITE_OWN = "assets:write_own"
    SOA_READ = "soa:read"
    SOA_WRITE = "soa:write"
    SOA_APPROVE = "soa:approve"
    DOCUMENTS_CREATE = "documents:create"
    AUDITS_WRITE = "audits:write"
    TRAINING_MANAGE = "training:manage"
    PRIVACY_MANAGE = "privacy:manage"


_READ_ALL = frozenset({Perm.CONTROLS_READ, Perm.RISKS_READ, Perm.ASSETS_READ, Perm.SOA_READ})

ROLE_PERMISSIONS: dict[Role, frozenset[Perm]] = {
    Role.PLATFORM_ADMIN: _READ_ALL | {Perm.USERS_MANAGE, Perm.SETTINGS_MANAGE, Perm.AUDIT_LOG_READ},
    Role.ISMS_MANAGER: _READ_ALL
    | {
        Perm.CONTROLS_WRITE,
        Perm.AUDIT_LOG_READ,
        Perm.EVIDENCE_REVIEW,
        Perm.RISKS_WRITE,
        Perm.RISKS_ACCEPT_HIGH,
        Perm.ASSETS_WRITE,
        Perm.SOA_WRITE,
        Perm.DOCUMENTS_CREATE,
        Perm.AUDITS_WRITE,
        Perm.TRAINING_MANAGE,
        Perm.PRIVACY_MANAGE,
    },
    Role.CONTROL_OWNER: _READ_ALL | {Perm.CONTROLS_WRITE_OWN, Perm.ASSETS_WRITE_OWN, Perm.DOCUMENTS_CREATE},
    Role.RISK_OWNER: _READ_ALL | {Perm.RISKS_WRITE_OWN, Perm.RISKS_ACCEPT_MEDIUM_OWN},
    Role.CONTRIBUTOR: _READ_ALL | {Perm.DOCUMENTS_CREATE},
    Role.INTERNAL_AUDITOR: _READ_ALL | {Perm.AUDIT_LOG_READ, Perm.AUDITS_WRITE},
    Role.EXTERNAL_AUDITOR: _READ_ALL,
    Role.EXECUTIVE: _READ_ALL | {Perm.RISKS_ACCEPT_CRITICAL, Perm.SOA_APPROVE},
    Role.EMPLOYEE: frozenset(),
    Role.VIEWER: _READ_ALL,
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
