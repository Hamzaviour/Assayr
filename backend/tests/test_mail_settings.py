import pytest
from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.mail.crypto import decrypt, encrypt
from assayr.mail.models import MailSettings
from tests import mail_helpers
from tests.conftest import create_user, sign_in

SETTINGS = {
    "enabled": True,
    "host": "mail.acme.local",
    "port": 587,
    "security": "starttls",
    "username": "assayr@acme.com",
    "password": "Invented-Secret-1",
    "from_address": "assayr@acme.com",
    "from_name": "Acme GRC",
    "base_url": "https://grc.acme.local",
    "digest_hour": 7,
}


@pytest.fixture
def admin(client, db, app):
    app.state.settings.secret_key = "invented-test-key"
    create_user(db, "root@acme.com", roles=(("platform_admin", None),), full_name="Root Admin")
    sign_in(client, "root@acme.com")


def test_settings_save_and_the_password_never_comes_back(client, db, admin):
    empty = client.get("/api/v1/settings/mail").json()
    assert empty["enabled"] is False and empty["password_set"] is False and "password" not in empty
    saved = client.put("/api/v1/settings/mail", json=SETTINGS)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["password_set"] is True and "password" not in body and "password_encrypted" not in body
    assert body["host"] == "mail.acme.local" and body["base_url"] == "https://grc.acme.local"
    stored = db.scalar(select(MailSettings))
    assert stored.password_encrypted and "Invented-Secret-1" not in stored.password_encrypted
    keep = client.put("/api/v1/settings/mail", json={k: v for k, v in SETTINGS.items() if k != "password"})
    assert keep.json()["password_set"] is True
    db.expire_all()
    assert (
        decrypt("invented-test-key", db.scalar(select(MailSettings)).password_encrypted)
        == "Invented-Secret-1"
    )
    cleared = client.put("/api/v1/settings/mail", json={**SETTINGS, "password": ""}).json()
    assert cleared["password_set"] is False
    trail = " ".join(str(e.diff) + str(e.reason) for e in db.scalars(select(AuditLog)))
    assert "Invented-Secret-1" not in trail


def test_validation(client, db, admin):
    put = lambda **c: client.put("/api/v1/settings/mail", json={**SETTINGS, **c})  # noqa: E731
    assert put(host="").status_code == 422
    assert put(from_address="not-an-address").status_code == 422
    assert put(base_url="grc.acme.local").status_code == 422
    assert put(digest_hour=24).status_code == 422
    assert put(port=0).status_code == 422
    assert put(security="tls9").status_code == 422
    assert put(enabled=False, host="", from_address="", base_url="").status_code == 200


def test_saving_a_password_needs_the_secret_key(client, db, admin, app):
    app.state.settings.secret_key = None
    r = client.put("/api/v1/settings/mail", json=SETTINGS)
    assert r.status_code == 409 and "ASSAYR_SECRET_KEY" in r.json()["detail"]


def test_only_platform_administrators(client, db, app):
    create_user(db, "sana@acme.com")
    sign_in(client, "sana@acme.com")
    assert client.get("/api/v1/settings/mail").status_code == 403
    assert client.put("/api/v1/settings/mail", json=SETTINGS).status_code == 403


def test_test_email_goes_to_the_administrator(client, db, admin, monkeypatch):
    sent = mail_helpers.install(monkeypatch)
    client.put("/api/v1/settings/mail", json=SETTINGS)
    r = client.post("/api/v1/settings/mail/test")
    assert r.status_code == 200 and r.json() == {"sent_to": "root@acme.com"}
    assert [(m["to"], m["host"], m["port"], m["tls"]) for m in sent] == [
        ("root@acme.com", "mail.acme.local", 587, True)
    ]
    assert sent[0]["from"] == "Acme GRC <assayr@acme.com>" and "test" in sent[0]["subject"].lower()
    mail_helpers.FakeSMTP.fail_login = True
    failed = client.post("/api/v1/settings/mail/test")
    assert failed.status_code == 502 and "bad credentials" in failed.json()["detail"]


def test_test_email_needs_settings(client, db, admin):
    r = client.post("/api/v1/settings/mail/test")
    assert r.status_code == 409


def test_digest_opt_out_is_personal(client, db, app):
    create_user(db, "omar@acme.com", roles=(("control_owner", None),))
    sign_in(client, "omar@acme.com")
    assert client.get("/api/v1/auth/me").json()["digest_opt_out"] is False
    r = client.patch("/api/v1/me/digest", json={"opt_out": True})
    assert r.status_code == 200 and r.json() == {"digest_opt_out": True}
    assert client.get("/api/v1/auth/me").json()["digest_opt_out"] is True


def test_encryption_round_trip_and_wrong_key():
    token = encrypt("key-one", "Invented")
    assert decrypt("key-one", token) == "Invented"
    assert decrypt("key-two", token) is None
