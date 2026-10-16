import pytest
from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from assayr.nia.seed import seed_nia
from tests.conftest import create_user, sign_in


@pytest.fixture
def nia(db, seeded):
    seed_nia(db, seeded)
    db.commit()
    return seeded


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def test_list_filters_by_domain(client, db, nia):
    manager(client, db)
    rows = client.get("/api/v1/nia/controls?domain=PS").json()
    assert [r["ref"] for r in rows][:3] == ["PS 1", "PS 2", "PS 3"] and len(rows) == 12
    ps8 = next(r for r in rows if r["ref"] == "PS 8")
    assert ps8["domain_name"] == "Personnel Security" and ps8["status"] == "not_started"
    assert sorted(m["code"] for m in ps8["mapped"]) == ["A.5.15", "A.8.3"]


def test_detail_has_summary_and_no_text_until_imported(client, db, nia):
    manager(client, db)
    body = client.get("/api/v1/nia/controls/PS 8").json()
    assert body["text"] is None and body["summary"] and body["can_edit"] is True
    assert client.get("/api/v1/nia/controls/ZZ 1").status_code == 404


def test_mapping_update_changes_status_and_is_audited(client, db, nia):
    manager(client, db)
    a51 = db.scalar(select(Control).where(Control.code == "A.5.1"))
    a51.status, a51.score = "compliant", 100.0
    db.commit()
    response = client.put(
        "/api/v1/nia/controls/PS 8/mapping", json={"links": [{"code": "A.5.1", "coverage": "full"}]}
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "compliant"
    assert response.json()["mapped"][0]["coverage"] == "full"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "nia.mapping")) is not None
    bad = client.put(
        "/api/v1/nia/controls/PS 8/mapping", json={"links": [{"code": "A.99.9", "coverage": "full"}]}
    )
    assert bad.status_code == 422


def test_only_managers_change_mapping_or_applicability(client, db, nia):
    create_user(db, "bilal@acme.com", roles=(("control_owner", None),), full_name="Bilal Khan")
    sign_in(client, "bilal@acme.com")
    assert client.get("/api/v1/nia/controls/PS 8").json()["can_edit"] is False
    assert client.put("/api/v1/nia/controls/PS 8/mapping", json={"links": []}).status_code == 403
    assert (
        client.post(
            "/api/v1/nia/controls/CS 11/applicability", json={"applicable": False, "reason": "x"}
        ).status_code
        == 403
    )


def test_applicability_needs_a_reason(client, db, nia):
    manager(client, db)
    url = "/api/v1/nia/controls/CS 11/applicability"
    assert client.post(url, json={"applicable": False}).status_code == 422
    body = client.post(url, json={"applicable": False, "reason": "We do not use fax machines"}).json()
    assert body["applicable"] is False and body["exclusion_reason"] == "We do not use fax machines"
    assert client.post(url, json={"applicable": True}).json()["applicable"] is True


def test_dashboard_shows_nia_after_iso(client, db, nia):
    manager(client, db)
    frameworks = client.get("/api/v1/dashboard").json()["frameworks"]
    assert [f["name"] for f in frameworks] == ["ISO/IEC 27001", "NIA"]
    assert frameworks[1]["total"] == 355 and len(frameworks[1]["groups"]) == 26
    ps = next(g for g in frameworks[1]["groups"] if g["name"] == "Personnel Security")
    assert ps["code"] == "PS"


def test_iso_views_do_not_include_nia_only_controls(client, db, nia):
    manager(client, db)
    assert client.get("/api/v1/controls/summary").json()["total"] == 93
    assert len(client.get("/api/v1/controls?limit=200").json()["items"]) == 93
    assert sum(client.get("/api/v1/readiness").json()["status_counts"].values()) == 93
    items = client.get("/api/v1/soa").json()["items"]
    assert len(items) == 93 and not any(i["code"].startswith("NIA ") for i in items)


def test_empty_mapping_is_refused(client, db, nia):
    manager(client, db)
    response = client.put("/api/v1/nia/controls/IG 1/mapping", json={"links": []})
    assert response.status_code == 422 and "at least one" in response.json()["detail"]


def test_nia_only_controls_report_their_own_control(client, db, nia):
    manager(client, db)
    body = client.get("/api/v1/nia/controls/RM 1").json()
    assert body["own_control"] == "NIA RM 1"
    assert client.get("/api/v1/nia/controls/PS 8").json()["own_control"] is None


def test_unowned_count_covers_iso_controls_only(client, db, nia):
    manager(client, db)
    assert client.get("/api/v1/dashboard").json()["unowned_controls"] == 93
