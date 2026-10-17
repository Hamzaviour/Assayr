from tests.conftest import create_user, sign_in


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def new_asset(client, **extra):
    body = {"name": "HR system", "type": "application", **extra}
    response = client.post("/api/v1/assets", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_levels_are_reported_in_words(client, db, seeded):
    manager(client, db)
    a = new_asset(client, confidentiality=5, integrity=2, availability=4)
    assert (a["confidentiality_label"], a["integrity_label"], a["availability_label"]) == (
        "Very high",
        "Low",
        "High",
    )
    assert a["criticality"] == 5 and a["criticality_label"] == "Very high"


def test_filter_by_minimum_criticality(client, db, seeded):
    manager(client, db)
    new_asset(client, name="Low thing", confidentiality=2, integrity=2, availability=1)
    new_asset(client, name="High thing", confidentiality=4, integrity=3, availability=3)
    new_asset(client, name="Crown jewels", confidentiality=5, integrity=5, availability=5)
    names = [a["name"] for a in client.get("/api/v1/assets?criticality=4").json()]
    assert names == ["High thing", "Crown jewels"]


def test_personal_data_with_a_sensitive_category_is_marked_sensitive(client, db, seeded):
    manager(client, db)
    a = new_asset(client, holds_pii=True, pii_categories=["hr", "health"], pii_volume="100_1k")
    assert a["holds_pii"] is True and a["pii_sensitive"] is True
    assert a["pii_categories"] == ["hr", "health"] and a["pii_volume"] == "100_1k"
    plain = new_asset(client, name="CRM", holds_pii=True, pii_categories=["contact"])
    assert plain["pii_sensitive"] is False
    manual = new_asset(client, name="Archive", holds_pii=True, pii_categories=["other"], pii_sensitive=True)
    assert manual["pii_sensitive"] is True


def test_unknown_values_are_refused(client, db, seeded):
    manager(client, db)
    bad = client.post(
        "/api/v1/assets",
        json={"name": "x", "type": "application", "holds_pii": True, "pii_categories": ["dna"]},
    )
    assert bad.status_code == 422
    vol = client.post(
        "/api/v1/assets", json={"name": "x", "type": "application", "holds_pii": True, "pii_volume": "lots"}
    )
    assert vol.status_code == 422


def test_switching_personal_data_off_clears_the_details(client, db, seeded):
    manager(client, db)
    a = new_asset(client, holds_pii=True, pii_categories=["health"], pii_volume="gt10k")
    body = client.patch(f"/api/v1/assets/{a['id']}", json={"holds_pii": False}).json()
    assert (body["holds_pii"], body["pii_categories"], body["pii_sensitive"], body["pii_volume"]) == (
        False,
        [],
        False,
        None,
    )
    assert client.get("/api/v1/assets?pii=true").json() == []


def test_pii_filter(client, db, seeded):
    manager(client, db)
    new_asset(client, name="Payroll", holds_pii=True, pii_categories=["financial"])
    new_asset(client, name="Web server", type="server")
    assert [a["name"] for a in client.get("/api/v1/assets?pii=true").json()] == ["Payroll"]


def test_owners_edit_personal_data_on_their_own_assets_only(client, db, seeded):
    owner = create_user(db, "omar@acme.com", roles=(("control_owner", None),), full_name="Omar")
    manager(client, db)
    mine = new_asset(client, name="Mine", owner_id=str(owner.id))
    theirs = new_asset(client, name="Theirs")
    sign_in(client, "omar@acme.com")
    ok = client.patch(f"/api/v1/assets/{mine['id']}", json={"holds_pii": True, "pii_categories": ["contact"]})
    assert ok.status_code == 200 and ok.json()["holds_pii"] is True
    assert client.patch(f"/api/v1/assets/{theirs['id']}", json={"holds_pii": True}).status_code == 403
