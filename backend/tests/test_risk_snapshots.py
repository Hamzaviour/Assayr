import io

import openpyxl
from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.exports import XLSX_MIME
from tests.conftest import create_user, sign_in
from tests.risk_helpers import assessed_risk


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def test_snapshot_freezes_the_register_and_compare_shows_changes(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=4, consequence=4, title="Ransomware")["code"]
    first = client.post("/api/v1/risk-snapshots", json={"label": "Q3 2026 assessment"})
    assert first.status_code == 201
    first = first.json()
    assert (first["risk_count"], first["rows"][0]["current"]["score"]) == (1, 16)
    clock.advance(minutes=5)
    client.patch(f"/api/v1/risks/{code}/assessment", json={"likelihood": 2})
    client.post(f"/api/v1/risks/{code}/assessment/finalize")
    second = client.post("/api/v1/risk-snapshots", json={"label": "Q4 2026 assessment"}).json()
    assert client.get(f"/api/v1/risk-snapshots/{first['id']}").json()["rows"][0]["current"]["score"] == 16
    diff = client.get(f"/api/v1/risk-snapshots/compare?base={first['id']}&head={second['id']}").json()
    assert (diff["added"], diff["removed"]) == ([], [])
    assert diff["changed"] == [
        {
            "code": code,
            "title": "Ransomware",
            "changes": [
                {"field": "current", "before": "High (16)", "after": "Medium (8)"},
                {"field": "target", "before": "High (16)", "after": "Medium (8)"},
            ],
        }
    ]
    assert [s["label"] for s in client.get("/api/v1/risk-snapshots").json()] == [
        "Q4 2026 assessment",
        "Q3 2026 assessment",
    ]


def test_snapshots_need_write_permission_to_create(client, db, seeded):
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    assert client.post("/api/v1/risk-snapshots", json={"label": "x"}).status_code == 403
    assert client.get("/api/v1/risk-snapshots").json() == []


def test_export_neutralises_formulas(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=4, consequence=4, title='=HYPERLINK("http://evil","click")')[
        "code"
    ]
    client.post(f"/api/v1/risks/{code}/treatment", json={"option": "modify"})
    client.post(f"/api/v1/risks/{code}/actions", json={"title": "Enable MFA"})
    response = client.get("/api/v1/risk-register/export.xlsx")
    assert response.status_code == 200 and response.headers["content-type"] == XLSX_MIME
    assert response.headers["content-disposition"].startswith("attachment")
    book = openpyxl.load_workbook(io.BytesIO(response.content))
    register = book["Register"]
    assert [c.value for c in register[1]][:3] == ["Code", "Risk", "Category"]
    assert register["B2"].value == '\'=HYPERLINK("http://evil","click")'
    assert register["G2"].value == "High (16)"
    assert book["Treatment plan"]["F2"].value == "Enable MFA"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "risk.export")) is not None
