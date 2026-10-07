from fastapi.testclient import TestClient
from sqlalchemy import select

from assayr.audit.models import AuditLog
from tests.conftest import create_user, sign_in

ADMIN = (("platform_admin", None),)


def test_admin_lists_users_and_others_are_forbidden(app, client, db):
    create_user(db, "admin@acme.com", roles=ADMIN)
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "admin@acme.com")
    assert [u["email"] for u in client.get("/api/v1/users").json()] == ["admin@acme.com", "viewer@acme.com"]
    with TestClient(app) as other:
        sign_in(other, "viewer@acme.com")
        response = other.get("/api/v1/users")
        assert response.status_code == 403
        assert response.json() == {"detail": "You don't have permission to do this."}


def test_created_user_can_sign_in_and_password_is_not_audited(app, client, db):
    create_user(db, "admin@acme.com", roles=ADMIN)
    sign_in(client, "admin@acme.com")
    response = client.post(
        "/api/v1/users",
        json={
            "email": "Bilal@Acme.com",
            "full_name": "Bilal Khan",
            "password": "another-long-password",
            "roles": [{"role": "control_owner"}],
        },
    )
    assert response.status_code == 201
    assert response.json()["email"] == "bilal@acme.com"
    entry = db.scalar(select(AuditLog).where(AuditLog.action == "user.create"))
    assert "another-long-password" not in str(entry.diff)
    with TestClient(app) as bilal:
        assert sign_in(bilal, "bilal@acme.com", "another-long-password").status_code == 200


def test_duplicate_email_rejected_case_insensitively(client, db):
    create_user(db, "admin@acme.com", roles=ADMIN)
    sign_in(client, "admin@acme.com")
    response = client.post(
        "/api/v1/users",
        json={"email": "ADMIN@acme.com", "full_name": "Dup", "password": "another-long-password"},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "A user with this email already exists."}


def test_weak_password_and_unknown_role_are_rejected(client, db):
    create_user(db, "admin@acme.com", roles=ADMIN)
    sign_in(client, "admin@acme.com")
    weak = client.post("/api/v1/users", json={"email": "x@acme.com", "full_name": "X", "password": "short"})
    assert weak.status_code == 422 and weak.json() == {"detail": "Use at least 12 characters."}
    bad_role = client.post(
        "/api/v1/users",
        json={
            "email": "y@acme.com",
            "full_name": "Y",
            "password": "another-long-password",
            "roles": [{"role": "wizard"}],
        },
    )
    assert bad_role.status_code == 422


def test_admin_cannot_deactivate_themselves(client, db):
    admin = create_user(db, "admin@acme.com", roles=ADMIN)
    sign_in(client, "admin@acme.com")
    response = client.patch(f"/api/v1/users/{admin.id}", json={"is_active": False})
    assert response.status_code == 409
    assert response.json() == {"detail": "You can't deactivate your own account."}


def test_deactivating_a_user_ends_their_sessions(app, client, db):
    create_user(db, "admin@acme.com", roles=ADMIN)
    bilal = create_user(db, "bilal@acme.com", roles=(("viewer", None),))
    with TestClient(app) as bilal_client:
        sign_in(bilal_client, "bilal@acme.com")
        sign_in(client, "admin@acme.com")
        assert client.patch(f"/api/v1/users/{bilal.id}", json={"is_active": False}).status_code == 200
        assert bilal_client.get("/api/v1/auth/me").status_code == 401


def test_roles_can_be_replaced_including_re_adding_an_existing_one(client, db):
    create_user(db, "admin@acme.com", roles=ADMIN)
    bilal = create_user(db, "bilal@acme.com", roles=(("viewer", None), ("contributor", None)))
    sign_in(client, "admin@acme.com")
    response = client.patch(
        f"/api/v1/users/{bilal.id}", json={"roles": [{"role": "viewer"}, {"role": "control_owner"}]}
    )
    assert response.status_code == 200
    assert sorted(r["role"] for r in response.json()["roles"]) == ["control_owner", "viewer"]
