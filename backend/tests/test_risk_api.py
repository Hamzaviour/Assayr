from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from tests.conftest import create_user, sign_in
from tests.risk_helpers import new_risk


def manager(client, db):
    user = create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")
    return user


def test_create_a_blank_risk(client, db, seeded):
    boss = manager(client, db)
    risk = new_risk(client, title="Ransomware encrypts file servers", owner_id=str(boss.id))
    assert (risk["code"], risk["status"], risk["owner"]["full_name"]) == ("R-001", "draft", "Sana Malik")
    assert risk["draft"]["likelihood"] is None and risk["latest"] is None and risk["can_edit"] is True
    assert [r["code"] for r in client.get("/api/v1/risks").json()] == ["R-001"]
    entry = db.scalar(select(AuditLog).where(AuditLog.action == "risk.create"))
    assert entry.diff == {"title": "Ransomware encrypts file servers", "template": None}


def test_create_from_a_template(client, db, seeded):
    manager(client, db)
    risk = client.post("/api/v1/risks", json={"template_code": "RT01"}).json()
    assert (risk["title"], risk["template_code"], risk["category"]) == (
        "Ransomware encrypts file servers",
        "RT01",
        "Cyber attack",
    )
    assert [t["code"] for t in risk["threats"]] == ["T01"]
    assert [c["code"] for c in risk["controls"]] == ["A.6.3", "A.8.7", "A.8.8", "A.8.13", "A.8.22"]
    assert risk["draft"]["likelihood"] == 3
    assert risk["draft"]["inherent"] == {
        "likelihood": 3,
        "consequence": 5,
        "score": 15,
        "band": "high",
        "band_label": "High",
    }
    assert risk["inherent"]["score"] == 15
    assert client.post("/api/v1/risks", json={"title": "Another"}).json()["code"] == "R-002"


def test_title_or_template_is_required_and_the_template_must_exist(client, db, seeded):
    manager(client, db)
    assert client.post("/api/v1/risks", json={}).status_code == 422
    response = client.post("/api/v1/risks", json={"template_code": "RT99"})
    assert response.status_code == 404 and response.json() == {"detail": "Risk template not found."}


def test_update_scenario_threats_and_assets(client, db, seeded):
    manager(client, db)
    asset = client.post("/api/v1/assets", json={"name": "File server", "type": "server"}).json()
    risk = new_risk(client)
    body = client.patch(
        f"/api/v1/risks/{risk['code']}",
        json={
            "title": "Ransomware",
            "approach": "asset",
            "threat_codes": ["T02", "T01"],
            "vulnerability_codes": ["V17"],
            "asset_ids": [asset["id"]],
        },
    ).json()
    assert (body["title"], body["approach"]) == ("Ransomware", "asset")
    assert [t["code"] for t in body["threats"]] == ["T01", "T02"]
    assert [v["code"] for v in body["vulnerabilities"]] == ["V17"]
    assert [a["code"] for a in body["assets"]] == ["AST-001"]
    response = client.patch(f"/api/v1/risks/{risk['code']}", json={"threat_codes": ["T99"]})
    assert response.status_code == 422 and response.json() == {"detail": "Unknown threat: T99."}


def test_linking_controls_replaces_the_set(client, db, seeded):
    manager(client, db)
    url = f"/api/v1/risks/{new_risk(client)['code']}/controls"
    body = client.put(
        url, json={"links": [{"code": "A.8.13"}, {"code": "A.8.7", "axis": "consequence"}]}
    ).json()
    assert [(c["code"], c["axis"], c["status"]) for c in body["controls"]] == [
        ("A.8.7", "consequence", "not_started"),
        ("A.8.13", "likelihood", "not_started"),
    ]
    body = client.put(url, json={"links": [{"code": "A.8.7"}]}).json()
    assert [(c["code"], c["axis"]) for c in body["controls"]] == [("A.8.7", "likelihood")]
    response = client.put(url, json={"links": [{"code": "A.9.99"}]})
    assert response.status_code == 404 and response.json() == {"detail": "Control A.9.99 not found."}
    response = client.put(url, json={"links": [{"code": "A.8.7"}, {"code": "A.8.7"}]})
    assert response.status_code == 422 and response.json() == {"detail": "Each control can be linked once."}


def test_excluded_controls_cannot_be_linked(client, db, seeded):
    manager(client, db)
    control = db.scalar(select(Control).where(Control.code == "A.8.30"))
    control.applicable, control.exclusion_reason = False, "No outsourced development"
    db.commit()
    response = client.put(
        f"/api/v1/risks/{new_risk(client)['code']}/controls", json={"links": [{"code": "A.8.30"}]}
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": "A.8.30 is excluded in the Statement of Applicability. Include it before linking it to a risk."
    }


def test_risk_owner_edits_only_their_own_risks(client, db, seeded):
    owner = create_user(db, "bilal@acme.com", roles=(("risk_owner", None),), full_name="Bilal Khan")
    boss = manager(client, db)
    mine = new_risk(client, title="Mine", owner_id=str(owner.id))
    theirs = new_risk(client, title="Theirs")
    sign_in(client, "bilal@acme.com")
    assert client.patch(f"/api/v1/risks/{mine['code']}", json={"description": "Updated"}).status_code == 200
    assert client.patch(f"/api/v1/risks/{theirs['code']}", json={"description": "x"}).status_code == 403
    response = client.patch(f"/api/v1/risks/{mine['code']}", json={"owner_id": str(boss.id)})
    assert response.status_code == 403
    assert response.json() == {"detail": "Only an ISMS manager can change the owner."}
    assert client.post("/api/v1/risks", json={"title": "New"}).status_code == 403
    assert client.get(f"/api/v1/risks/{theirs['code']}").json()["can_edit"] is False


def test_list_filters_and_read_only_roles(client, db, seeded):
    boss = manager(client, db)
    new_risk(client, title="Ransomware", owner_id=str(boss.id))
    new_risk(client, title="Flood")
    assert [r["title"] for r in client.get("/api/v1/risks?owner=me").json()] == ["Ransomware"]
    assert [r["title"] for r in client.get("/api/v1/risks?q=flo").json()] == ["Flood"]
    assert len(client.get("/api/v1/risks?status=draft").json()) == 2
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    assert len(client.get("/api/v1/risks").json()) == 2
    assert client.post("/api/v1/risks", json={"title": "x"}).status_code == 403
    assert client.get("/api/v1/risks/R-404").status_code == 404


def test_owner_none_lists_unassigned_risks(client, db, seeded):
    manager(client, db)
    me = client.get("/api/v1/auth/me").json()
    mine = new_risk(client, title="Owned")
    client.patch(f"/api/v1/risks/{mine['code']}", json={"owner_id": me["id"]})
    new_risk(client, title="Nobody's")
    titles = [r["title"] for r in client.get("/api/v1/risks?owner=none").json()]
    assert titles == ["Nobody's"]
