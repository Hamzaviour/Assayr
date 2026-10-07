from sqlalchemy import update

from assayr.audit.models import AuditLog
from tests.conftest import create_user, sign_in


def test_audit_log_lists_newest_first_and_verifies(client, db):
    create_user(db, "sana@acme.com")
    sign_in(client, "sana@acme.com")
    page = client.get("/api/v1/audit-log").json()
    assert page["items"][0]["action"] == "auth.login"
    assert client.get("/api/v1/audit-log/verify").json() == {"ok": True, "checked": 1, "first_bad_seq": None}


def test_verify_reports_tampering(client, db):
    create_user(db, "sana@acme.com")
    sign_in(client, "sana@acme.com")
    db.execute(update(AuditLog).values(actor_email="mallory@acme.com"))
    db.commit()
    assert client.get("/api/v1/audit-log/verify").json()["ok"] is False


def test_audit_log_needs_permission(client, db):
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    assert client.get("/api/v1/audit-log").status_code == 403
