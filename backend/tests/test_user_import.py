from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.identity.models import User
from tests.conftest import create_user, sign_in


def admin(client, db):
    create_user(db, "admin@acme.com", roles=(("platform_admin", None),), full_name="Admin")
    sign_in(client, "admin@acme.com")


def upload(client, text: str | bytes, name="staff.csv"):
    data = text.encode("utf-8") if isinstance(text, str) else text
    return client.post("/api/v1/users/import", files={"file": (name, data, "text/csv")})


def test_import_creates_employees_with_temporary_passwords(client, db, seeded):
    admin(client, db)
    response = upload(
        client,
        "name,email,department,role\nOmar Ali,omar@acme.com,Finance,\nNadia Noor,nadia@acme.com,IT,contributor\n",
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [c["email"] for c in body["created"]] == ["omar@acme.com", "nadia@acme.com"] and body[
        "skipped"
    ] == []
    temp = body["created"][0]["temporary_password"]
    assert len(temp) == 16
    omar = db.scalar(select(User).where(User.email == "omar@acme.com"))
    assert omar.department == "Finance" and omar.must_change_password is True
    assert [a.role for a in omar.role_assignments] == ["employee"]
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    assert sign_in(client, "omar@acme.com", temp).status_code == 200
    assert client.get("/api/v1/auth/me").json()["must_change_password"] is True


def test_duplicates_and_bad_rows_are_reported_with_line_numbers(client, db, seeded):
    admin(client, db)
    csv = (
        "name,email,department,role\n"
        "Omar Ali,omar@acme.com,Finance,\n"
        "Omar Again,OMAR@acme.com,Finance,\n"
        "Admin Copy,admin@acme.com,,\n"
        "No Email,not-an-email,,\n"
        "Bad Role,bad@acme.com,,wizard\n"
        ",noname@acme.com,,\n"
    )
    body = upload(client, csv).json()
    assert [c["email"] for c in body["created"]] == ["omar@acme.com"]
    reasons = {s["line"]: s["reason"] for s in body["skipped"]}
    assert set(reasons) == {3, 4, 5, 6, 7}
    assert "already" in reasons[3] and "already" in reasons[4] and "email" in reasons[5].lower()
    assert "role" in reasons[6].lower() and "name" in reasons[7].lower()


def test_a_csv_saved_by_excel_imports_cleanly(client, db, seeded):
    admin(client, db)
    data = "﻿name;email;department;role\r\nOmar Ali;omar@acme.com;Finance;employee\r\n\r\n\r\n".encode()
    body = upload(client, data).json()
    assert [c["email"] for c in body["created"]] == ["omar@acme.com"] and body["skipped"] == []


def test_a_csv_without_the_header_is_refused(client, db, seeded):
    admin(client, db)
    response = upload(client, "who,mail\nOmar,omar@acme.com\n")
    assert response.status_code == 422 and "name" in response.json()["detail"]


def test_import_limits(client, db, seeded):
    admin(client, db)
    assert upload(client, b"x" * (1024 * 1024 + 1)).status_code == 413
    rows = "name,email\n" + "".join(f"P{i},p{i}@acme.com\n" for i in range(2001))
    assert upload(client, rows).status_code == 422


def test_only_user_admins_import_and_passwords_never_reach_the_audit_log(client, db, seeded):
    create_user(db, "sana@acme.com", full_name="Sana")
    sign_in(client, "sana@acme.com")
    assert upload(client, "name,email\nOmar,omar@acme.com\n").status_code == 403
    admin(client, db)
    body = upload(client, "name,email\nOmar,omar@acme.com\n").json()
    log = db.scalar(select(AuditLog).where(AuditLog.action == "user.import"))
    assert log is not None and log.diff["created"] == [None, 1]
    assert body["created"][0]["temporary_password"] not in str(log.diff)
