from tests.conftest import create_user, sign_in

BODY = {
    "name": "Invoice classifier",
    "purpose": "Sort invented invoices",
    "source": "in_house",
    "model_type": "classification",
    "lifecycle": "deployed",
    "risk_level": 3,
    "uses_personal_data": True,
    "pii_categories": ["contact"],
}


def manager(client, db):
    return create_user(db, "ana@acme.com")


def test_register_crud_and_codes(client, db, seeded):
    user = manager(client, db)
    sign_in(client, "ana@acme.com")
    a = client.post("/api/v1/ai/systems", json={**BODY, "owner_id": str(user.id)}).json()
    b = client.post(
        "/api/v1/ai/systems",
        json={**BODY, "name": "Chat helper", "source": "third_party", "provider": "Invented Labs"},
    ).json()
    assert (a["code"], b["code"]) == ("AIS-001", "AIS-002")
    assert a["risk_label"] == "Medium" and a["owner"]["full_name"] == "Test User" and a["can_edit"] is True
    assert a["assessment_status"] is None and a["status"] == "active"
    r = client.patch(f"/api/v1/ai/systems/{a['id']}", json={"lifecycle": "retired", "status": "retired"})
    assert (r.json()["lifecycle"], r.json()["status"]) == ("retired", "retired")
    assert [s["code"] for s in client.get("/api/v1/ai/systems").json()] == ["AIS-001", "AIS-002"]
    assert client.get(f"/api/v1/ai/systems/{b['id']}").json()["provider"] == "Invented Labs"
    assert client.delete(f"/api/v1/ai/systems/{b['id']}").status_code == 204
    assert client.get(f"/api/v1/ai/systems/{b['id']}").status_code == 404


def test_validation(client, db, seeded):
    manager(client, db)
    sign_in(client, "ana@acme.com")
    assert client.post("/api/v1/ai/systems", json={**BODY, "pii_categories": ["nope"]}).status_code == 422
    assert client.post("/api/v1/ai/systems", json={**BODY, "risk_level": 6}).status_code == 422
    assert client.post("/api/v1/ai/systems", json={**BODY, "lifecycle": "flying"}).status_code == 422
    assert client.post("/api/v1/ai/systems", json={**BODY, "name": " "}).status_code == 422
    bad_asset = {**BODY, "asset_ids": ["00000000-0000-0000-0000-000000000000"]}
    assert client.post("/api/v1/ai/systems", json=bad_asset).status_code == 422
    no_personal = client.post("/api/v1/ai/systems", json={**BODY, "uses_personal_data": False}).json()
    assert no_personal["pii_categories"] == []


def test_only_managers_write(client, db, seeded):
    create_user(db, "vi@acme.com", roles=(("viewer", None),))
    sign_in(client, "vi@acme.com")
    assert client.get("/api/v1/ai/systems").status_code == 200
    assert client.post("/api/v1/ai/systems", json=BODY).status_code == 403
