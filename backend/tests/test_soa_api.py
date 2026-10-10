from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from tests.conftest import create_user, sign_in
from tests.risk_helpers import assessed_risk, new_risk


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def item(body, code):
    return next(i for i in body["items"] if i["code"] == code)


def test_soa_lists_every_control_with_risk_justifications(client, db, seeded):
    manager(client, db)
    client.put(f"/api/v1/risks/{new_risk(client)['code']}/controls", json={"links": [{"code": "A.8.13"}]})
    body = client.get("/api/v1/soa").json()
    assert len(body["items"]) == 93
    backup = item(body, "A.8.13")
    assert backup["sources"] == [{"kind": "risk", "label": "Risk R-001", "ref": "R-001"}]
    assert (backup["evidence_verified"], backup["evidence_required"]) == (0, 3)
    assert "A.8.13" not in body["checks"]["orphans"] and len(body["checks"]["orphans"]) == 92
    assert body["checks"]["ok"] is False


def test_bulk_sources_clear_orphans(client, db, seeded):
    manager(client, db)
    codes = [i["code"] for i in client.get("/api/v1/soa").json()["items"]]
    body = client.patch(
        "/api/v1/soa/items",
        json={
            "codes": codes,
            "sources": ["legal", "best_practice"],
            "justification": "Baseline for a regulated bank.",
        },
    ).json()
    assert body["checks"] == {"orphans": [], "excluded_mitigating": [], "untreated_risks": [], "ok": True}
    assert body["items"][0]["sources"] == [
        {"kind": "best_practice", "label": "Best practice", "ref": None},
        {"kind": "legal", "label": "Legal or regulatory", "ref": None},
    ]
    assert body["items"][0]["justification"] == "Baseline for a regulated bank."


def test_excluding_needs_a_reason_and_drops_the_control(client, db, seeded):
    manager(client, db)
    response = client.patch("/api/v1/soa/items", json={"codes": ["A.8.30"], "applicable": False})
    assert response.status_code == 422 and response.json() == {
        "detail": "Give a reason for excluding a control."
    }
    body = client.patch(
        "/api/v1/soa/items",
        json={
            "codes": ["A.8.30"],
            "applicable": False,
            "exclusion_reason": "All development is done in-house.",
        },
    ).json()
    excluded = item(body, "A.8.30")
    assert (excluded["applicable"], excluded["status"]) == (False, "excluded")
    assert "A.8.30" not in body["checks"]["orphans"]
    assert client.get("/api/v1/controls/A.8.30").json()["status"] == "excluded"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "soa.update")).diff["applicable"] == [
        True,
        False,
    ]
    back = client.patch("/api/v1/soa/items", json={"codes": ["A.8.30"], "applicable": True}).json()
    assert item(back, "A.8.30")["status"] == "not_started"


def test_excluding_a_control_that_mitigates_a_risk_is_refused(client, db, seeded):
    manager(client, db)
    for _ in range(2):
        client.put(f"/api/v1/risks/{new_risk(client)['code']}/controls", json={"links": [{"code": "A.8.13"}]})
    response = client.patch(
        "/api/v1/soa/items", json={"codes": ["A.8.13"], "applicable": False, "exclusion_reason": "x"}
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": "A.8.13 mitigates R-001, R-002. Unlink it from those risks or change their treatment first."
    }


def test_excluded_control_that_mitigates_a_risk_is_reported(client, db, seeded):
    manager(client, db)
    client.put(f"/api/v1/risks/{new_risk(client)['code']}/controls", json={"links": [{"code": "A.8.13"}]})
    control = db.scalar(select(Control).where(Control.code == "A.8.13"))
    control.applicable, control.exclusion_reason = False, "x"
    db.commit()
    checks = client.get("/api/v1/soa").json()["checks"]
    assert checks["excluded_mitigating"] == [{"code": "A.8.13", "risks": ["R-001"]}]


def test_untreated_risks_above_appetite_are_reported(client, db, seeded, clock):
    manager(client, db)
    high = assessed_risk(client, likelihood=4, consequence=4)["code"]
    assessed_risk(client, likelihood=1, consequence=2)
    assert client.get("/api/v1/soa").json()["checks"]["untreated_risks"] == [high]
    client.post(f"/api/v1/risks/{high}/treatment", json={"option": "modify"})
    assert client.get("/api/v1/soa").json()["checks"]["untreated_risks"] == []


def test_soa_permissions(client, db, seeded):
    manager(client, db)
    response = client.patch("/api/v1/soa/items", json={"codes": ["A.9.99"], "sources": ["legal"]})
    assert response.status_code == 404 and response.json() == {"detail": "Control A.9.99 not found."}
    for email, role in (("viewer@acme.com", "viewer"), ("tariq@acme.com", "executive")):
        create_user(db, email, roles=((role, None),))
        sign_in(client, email)
        assert client.get("/api/v1/soa").status_code == 200
        assert (
            client.patch("/api/v1/soa/items", json={"codes": ["A.5.1"], "sources": ["legal"]}).status_code
            == 403
        )
