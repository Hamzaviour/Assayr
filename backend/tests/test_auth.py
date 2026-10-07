from sqlalchemy import func, select

from assayr.audit.models import AuditLog
from assayr.identity.models import UserSession
from tests.conftest import PASSWORD, create_user, sign_in

GENERIC = "Email or password is incorrect, or the account is temporarily locked."


def test_login_sets_http_only_session_cookie_and_returns_permissions(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    response = sign_in(client, "sana@acme.com")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "sana@acme.com"
    assert "controls:write" in body["permissions"]
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("assayr_session="))
    assert "HttpOnly" in session_cookie and "SameSite=strict" in session_cookie
    csrf_cookie = next(c for c in cookies if c.startswith("assayr_csrf="))
    assert "HttpOnly" not in csrf_cookie


def test_secure_flag_is_set_when_configured(app, client, db):
    app.state.settings = app.state.settings.model_copy(update={"secure_cookies": True})
    create_user(db, "sana@acme.com")
    response = client.post("/api/v1/auth/login", json={"email": "sana@acme.com", "password": PASSWORD})
    assert all("Secure" in c for c in response.headers.get_list("set-cookie"))


def test_me_requires_a_session(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not signed in."}


def test_login_is_case_insensitive(client, db):
    create_user(db, "sana@acme.com")
    assert sign_in(client, "  Sana@ACME.com ").status_code == 200


def test_unknown_and_wrong_password_look_identical(client, db):
    create_user(db, "sana@acme.com")
    unknown = sign_in(client, "nobody@acme.com")
    wrong = sign_in(client, "sana@acme.com", "not-the-right-password")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json() == {"detail": GENERIC}


def test_lockout_after_five_failures(client, db, clock):
    create_user(db, "sana@acme.com")
    for _ in range(5):
        assert sign_in(client, "sana@acme.com", "not-the-right-password").status_code == 401
    locked = sign_in(client, "sana@acme.com")
    assert locked.status_code == 401 and locked.json() == {"detail": GENERIC}
    clock.advance(minutes=16)
    assert sign_in(client, "sana@acme.com").status_code == 200


def test_inactive_user_cannot_sign_in(client, db):
    create_user(db, "gone@acme.com", active=False)
    assert sign_in(client, "gone@acme.com").status_code == 401


def test_logout_requires_csrf_and_ends_the_session(client, db):
    create_user(db, "sana@acme.com")
    sign_in(client, "sana@acme.com")
    token = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": token}).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_idle_session_expires(client, db, clock):
    create_user(db, "sana@acme.com")
    sign_in(client, "sana@acme.com")
    clock.advance(minutes=31)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Your session has expired. Sign in again."}
    assert db.scalar(select(func.count()).select_from(UserSession)) == 0


def test_active_session_still_ends_after_twelve_hours(client, db, clock):
    create_user(db, "sana@acme.com")
    sign_in(client, "sana@acme.com")
    for _ in range(35):
        clock.advance(minutes=20)
        assert client.get("/api/v1/auth/me").status_code == 200
    clock.advance(minutes=20)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_sign_in_and_failures_are_audited(client, db):
    create_user(db, "sana@acme.com")
    sign_in(client, "sana@acme.com", "not-the-right-password")
    sign_in(client, "sana@acme.com")
    actions = list(db.scalars(select(AuditLog.action).order_by(AuditLog.seq)))
    assert actions == ["auth.login_failed", "auth.login"]
