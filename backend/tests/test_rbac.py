import uuid

from assayr.identity.rbac import ROLE_PERMISSIONS, Perm, Role, grant_for, permissions_for


def test_every_role_has_an_entry():
    assert set(ROLE_PERMISSIONS) == set(Role)


def test_global_assignment_grants_every_scope():
    grant = grant_for([("isms_manager", None)], Perm.CONTROLS_WRITE)
    assert grant.all_scopes and grant.allows(uuid.uuid4())


def test_scoped_assignment_only_grants_its_scope():
    scope = uuid.uuid4()
    grant = grant_for([("viewer", scope)], Perm.CONTROLS_READ)
    assert grant.any and not grant.all_scopes
    assert grant.allows(scope)
    assert not grant.allows(uuid.uuid4())


def test_role_without_permission_grants_nothing():
    assert not grant_for([("employee", None)], Perm.CONTROLS_READ).any


def test_unknown_role_strings_are_ignored():
    assert not grant_for([("legacy_role", None)], Perm.CONTROLS_READ).any
    assert permissions_for([("legacy_role", None), ("viewer", None)]) == ["controls:read"]


def test_permissions_are_a_sorted_union():
    assert permissions_for([("platform_admin", None), ("isms_manager", None)]) == [
        "audit_log:read",
        "controls:read",
        "controls:write",
        "settings:manage",
        "users:manage",
    ]
