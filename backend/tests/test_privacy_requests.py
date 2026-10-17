from tests.conftest import create_user, sign_in

REQUEST = {
    "type": "access",
    "requester_name": "Invented Person",
    "requester_contact": "person@example.com",
    "channel": "email",
    "received_on": "2026-01-31",
}


def officer(client, db):
    create_user(db, "dpo@acme.com", roles=(("privacy_officer", None),), full_name="Dana DPO")
    sign_in(client, "dpo@acme.com")


def new(client, **extra):
    response = client.post("/api/v1/privacy/requests", json={**REQUEST, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_codes_and_the_default_due_date(client, db, seeded):
    officer(client, db)
    r = new(client)
    assert r["code"] == "DSR-001" and r["due_on"] == "2026-03-02" and r["status"] == "open"
    assert new(client, type="erasure")["code"] == "DSR-002"
    assert [x["code"] for x in client.get("/api/v1/privacy/requests").json()] == ["DSR-001", "DSR-002"]


def test_overdue_and_days_left(client, db, seeded, clock):
    officer(client, db)
    today = clock.now.date()
    r = new(client, received_on=str(today), due_on=str(today))
    assert r["overdue"] is False and r["days_left"] == 0
    clock.advance(days=1)
    sign_in(client, "dpo@acme.com")
    again = client.get(f"/api/v1/privacy/requests/{r['id']}").json()
    assert again["overdue"] is True and again["days_left"] == -1


def test_steps_and_closing(client, db, seeded):
    officer(client, db)
    r = new(client)
    url = f"/api/v1/privacy/requests/{r['id']}"
    body = client.patch(
        url,
        json={
            "steps": [{"text": "Verify identity", "done": True}, {"text": "Collect data", "done": False}],
            "identity_verified": True,
        },
    ).json()
    assert body["status"] == "in_progress" and body["steps"][0]["done"] is True
    assert client.post(f"{url}/close", json={}).status_code == 422
    assert client.post(f"{url}/close", json={"outcome": "refused"}).status_code == 422
    closed = client.post(
        f"{url}/close",
        json={"outcome": "refused", "refusal_reason": "Manifestly unfounded", "response": "Invented reply"},
    ).json()
    assert (
        closed["status"] == "closed"
        and closed["outcome"] == "refused"
        and closed["closed_on"]
        and closed["overdue"] is False
    )


def test_linked_activities_must_be_ours(client, db, seeded):
    officer(client, db)
    a = client.post("/api/v1/privacy/activities", json={"name": "CRM", "lawful_basis": "consent"}).json()
    r = new(client, activity_ids=[a["id"]])
    assert [x["code"] for x in r["activities"]] == ["PA-001"]
    bad = client.post(
        "/api/v1/privacy/requests", json={**REQUEST, "activity_ids": ["00000000-0000-0000-0000-000000000001"]}
    )
    assert bad.status_code == 422


def test_unknown_type_is_refused(client, db, seeded):
    officer(client, db)
    assert (
        client.post("/api/v1/privacy/requests", json={**REQUEST, "type": "delete-everything"}).status_code
        == 422
    )


def test_requests_are_hidden_from_people_without_sensitive_access(client, db, seeded):
    officer(client, db)
    r = new(client)
    create_user(db, "vera@acme.com", roles=(("viewer", None),), full_name="Vera")
    sign_in(client, "vera@acme.com")
    assert client.get("/api/v1/privacy/requests").status_code == 403
    assert client.get(f"/api/v1/privacy/requests/{r['id']}").status_code == 403
    summary = client.get("/api/v1/privacy/summary").json()
    assert summary["requests_open"] == 1
