from assayr.identity.rbac import permissions_for
from tests.conftest import create_user, sign_in

PROCESSOR = {
    "name": "PayCo",
    "service": "Payroll processing",
    "country": "Qatar",
    "data_categories": ["financial", "hr"],
    "dpa_signed": True,
    "dpa_date": "2026-01-15",
    "security_result": "satisfactory",
    "risk_level": 2,
}


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def test_privacy_officer_role():
    perms = permissions_for([("privacy_officer", None)])
    assert {"assets:read", "controls:read", "privacy:manage", "privacy:sensitive"} <= set(perms)
    assert "privacy:sensitive" in permissions_for([("isms_manager", None)])
    assert "privacy:sensitive" not in permissions_for([("viewer", None)])


def test_processor_register(client, db, seeded):
    manager(client, db)
    created = client.post("/api/v1/privacy/processors", json=PROCESSOR)
    assert created.status_code == 201, created.text
    p = created.json()
    assert p["name"] == "PayCo" and p["status"] == "active" and p["risk_level_label"] == "Low"
    assert [r["name"] for r in client.get("/api/v1/privacy/processors").json()] == ["PayCo"]
    edited = client.patch(f"/api/v1/privacy/processors/{p['id']}", json={"status": "ended"}).json()
    assert edited["status"] == "ended"


def test_processor_validation(client, db, seeded):
    manager(client, db)
    for bad in ({"data_categories": ["dna"]}, {"security_result": "great"}, {"risk_level": 9}):
        assert client.post("/api/v1/privacy/processors", json={**PROCESSOR, **bad}).status_code == 422, bad


def test_activities_list_their_processors(client, db, seeded):
    manager(client, db)
    p = client.post("/api/v1/privacy/processors", json=PROCESSOR).json()
    a = client.post("/api/v1/privacy/activities", json={"name": "Payroll", "lawful_basis": "contract"}).json()
    response = client.put(
        f"/api/v1/privacy/activities/{a['id']}/processors", json={"processor_ids": [p["id"]]}
    )
    assert response.status_code == 200, response.text
    assert [x["name"] for x in response.json()["processors"]] == ["PayCo"]
    assert [x["code"] for x in client.get(f"/api/v1/privacy/processors/{p['id']}").json()["activities"]] == [
        "PA-001"
    ]


def test_viewers_read_processors_only(client, db, seeded):
    manager(client, db)
    client.post("/api/v1/privacy/processors", json=PROCESSOR)
    create_user(db, "vera@acme.com", roles=(("viewer", None),), full_name="Vera")
    sign_in(client, "vera@acme.com")
    assert len(client.get("/api/v1/privacy/processors").json()) == 1
    assert client.post("/api/v1/privacy/processors", json=PROCESSOR).status_code == 403
