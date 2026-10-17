from datetime import timedelta

from sqlalchemy import select

from assayr.audit.models import AuditLog
from tests.findings_helpers import (
    AUDITOR,
    DOER,
    MANAGER,
    OWNER,
    as_,
    audit_with_results,
    people,
    raise_finding,
)


def test_raising_from_an_audit_row_uses_the_defaults(client, db, seeded, clock):
    people(db)
    as_(client, AUDITOR)
    audit, items = audit_with_results(client)
    r = client.post("/api/v1/findings", json={"audit_item_id": items["A.5.1"]["id"]})
    assert r.status_code == 201, r.text
    f = r.json()
    assert (f["code"], f["grade"], f["status"], f["ref"], f["framework"]) == (
        "F-001",
        "major",
        "open",
        "A.5.1",
        "iso27001",
    )
    assert f["title"] == "A.5.1: Fail" and f["audit"] == {
        "id": audit["id"],
        "title": "Invented internal audit",
    }
    assert f["due_date"] == (clock.now.date() + timedelta(days=30)).isoformat()
    partial = raise_finding(client, items["A.5.2"]["id"], title="Invented title", owner_id=None)
    assert (partial["code"], partial["grade"], partial["title"]) == ("F-002", "minor", "Invented title")
    assert partial["due_date"] == (clock.now.date() + timedelta(days=90)).isoformat()


def test_raising_twice_returns_the_same_finding(client, db, seeded):
    people(db)
    as_(client, AUDITOR)
    _, items = audit_with_results(client)
    first = client.post("/api/v1/findings", json={"audit_item_id": items["A.5.1"]["id"]})
    again = client.post("/api/v1/findings", json={"audit_item_id": items["A.5.1"]["id"]})
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["id"] == again.json()["id"]
    assert len(client.get("/api/v1/findings").json()) == 1


def test_only_failed_results_can_be_raised(client, db, seeded):
    people(db)
    as_(client, AUDITOR)
    _, items = audit_with_results(client)
    r = client.post("/api/v1/findings", json={"audit_item_id": items["A.5.3"]["id"]})
    assert r.status_code == 422
    assert r.json()["detail"] == "Only fail, partial or exception results can be raised as findings."


def test_full_capa_lifecycle(client, db, seeded, clock):
    who = people(db)
    as_(client, AUDITOR)
    _, items = audit_with_results(client)
    f = raise_finding(client, items["A.5.1"]["id"], owner_id=str(who["owner"].id))
    url = f"/api/v1/findings/{f['id']}"

    as_(client, OWNER)
    assert client.patch(url, json={"root_cause": "Invented root cause"}).json()["status"] == "open"
    assert client.patch(url, json={"grade": "minor"}).status_code == 403
    action = client.post(
        f"{url}/actions", json={"description": "Invented fix", "owner_id": str(who["doer"].id)}
    )
    assert action.status_code == 201, action.text
    action = action.json()
    assert client.get(url).json()["status"] == "action_planned"

    as_(client, DOER)
    done = client.patch(f"{url}/actions/{action['id']}", json={"status": "done"})
    assert done.status_code == 422 and done.json()["detail"] == "Add a note or a file showing what was done."
    done = client.patch(
        f"{url}/actions/{action['id']}", json={"status": "done", "done_note": "Invented proof"}
    )
    assert done.status_code == 200 and done.json()["status"] == "done"
    assert client.get(url).json()["status"] == "awaiting_verification"
    denied = client.post(f"{url}/verify", json={"effective": True, "note": "Looks fine"})
    assert denied.status_code == 403

    as_(client, AUDITOR)
    back = client.post(f"{url}/verify", json={"effective": False, "note": "Invented: still happening"})
    assert back.status_code == 200 and back.json()["status"] == "action_planned"
    assert [v["effective"] for v in back.json()["verifications"]] == [False]
    clock.advance(hours=2)

    as_(client, OWNER)
    second = client.post(
        f"{url}/actions", json={"description": "Invented second fix", "owner_id": str(who["owner"].id)}
    )
    assert client.get(url).json()["status"] == "action_planned"
    client.patch(f"{url}/actions/{second.json()['id']}", json={"status": "done", "done_note": "Invented"})
    assert client.get(url).json()["status"] == "awaiting_verification"

    as_(client, AUDITOR)
    closed = client.post(f"{url}/verify", json={"effective": True, "note": "Invented: effective"}).json()
    assert closed["status"] == "closed" and closed["closed_at"] is not None
    assert client.patch(url, json={"title": "Changed"}).status_code == 409

    assert client.post(f"{url}/reopen", json={"reason": "Invented"}).status_code == 403
    as_(client, MANAGER)
    assert client.post(f"{url}/reopen", json={"reason": " "}).status_code == 422
    reopened = client.post(f"{url}/reopen", json={"reason": "Invented recurrence"}).json()
    assert reopened["status"] == "action_planned" and reopened["closed_at"] is None
    actions = [a for a in db.scalars(select(AuditLog.action).where(AuditLog.entity_type == "finding"))]
    assert {"finding.raise", "finding.verify", "finding.reopen"} <= set(actions)


def test_owners_of_the_work_can_not_verify_it(client, db, seeded):
    who = people(db)
    as_(client, AUDITOR)
    _, items = audit_with_results(client)
    f = raise_finding(client, items["A.5.1"]["id"], owner_id=str(who["owner"].id), root_cause="Invented")
    url = f"/api/v1/findings/{f['id']}"
    a = client.post(
        f"{url}/actions", json={"description": "Invented", "owner_id": str(who["auditor"].id)}
    ).json()
    client.patch(f"{url}/actions/{a['id']}", json={"status": "done", "done_note": "Invented"})
    denied = client.post(f"{url}/verify", json={"effective": True, "note": "x"})
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Someone who did not own this finding or its actions must verify it."
    assert client.get(url).json()["can_verify"] is False
    as_(client, MANAGER)
    assert client.get(url).json()["can_verify"] is True


def test_verification_waits_for_every_action(client, db, seeded):
    who = people(db)
    as_(client, AUDITOR)
    _, items = audit_with_results(client)
    f = raise_finding(client, items["A.5.1"]["id"], owner_id=str(who["owner"].id), root_cause="Invented")
    url = f"/api/v1/findings/{f['id']}"
    for _ in range(2):
        client.post(f"{url}/actions", json={"description": "Invented", "owner_id": str(who["doer"].id)})
    r = client.post(f"{url}/verify", json={"effective": True, "note": "x"})
    assert r.status_code == 409 and r.json()["detail"] == "2 corrective actions are still open."


def test_observations_close_with_a_response(client, db, seeded):
    who = people(db)
    as_(client, AUDITOR)
    _, items = audit_with_results(client)
    nc = raise_finding(client, items["A.5.1"]["id"])
    r = client.post(f"/api/v1/findings/{nc['id']}/close", json={"response": "x"})
    assert (
        r.status_code == 409
        and r.json()["detail"] == "Major and minor nonconformities close through verification."
    )
    obs = raise_finding(client, items["A.5.2"]["id"], grade="observation", owner_id=str(who["owner"].id))
    assert obs["status"] == "open"
    as_(client, OWNER)
    assert client.post(f"/api/v1/findings/{obs['id']}/close", json={"response": " "}).status_code == 422
    closed = client.post(
        f"/api/v1/findings/{obs['id']}/close", json={"response": "Invented: accepted"}
    ).json()
    assert (closed["status"], closed["response"]) == ("closed", "Invented: accepted")


def test_read_and_write_rights(client, db, seeded):
    who = people(db)
    as_(client, AUDITOR)
    _, items = audit_with_results(client)
    f = raise_finding(client, items["A.5.1"]["id"], owner_id=str(who["owner"].id), root_cause="Invented")
    action = client.post(
        f"/api/v1/findings/{f['id']}/actions",
        json={"description": "Invented", "owner_id": str(who["owner"].id)},
    ).json()
    as_(client, DOER)
    assert client.get(f"/api/v1/findings/{f['id']}").status_code == 200
    assert client.post("/api/v1/findings", json={"audit_item_id": items["A.5.2"]["id"]}).status_code == 403
    assert client.patch(f"/api/v1/findings/{f['id']}", json={"root_cause": "x"}).status_code == 403
    done = {"status": "done", "done_note": "x"}
    assert client.patch(f"/api/v1/findings/{f['id']}/actions/{action['id']}", json=done).status_code == 403
    detail = client.get(f"/api/v1/findings/{f['id']}").json()
    assert (
        detail["can_edit"] is False
        and detail["can_verify"] is False
        and detail["actions"][0]["can_complete"] is False
    )


def test_raise_as_risk_once(client, db, seeded):
    people(db)
    as_(client, AUDITOR)
    _, items = audit_with_results(client)
    f = raise_finding(client, items["A.5.1"]["id"])
    first = client.post(f"/api/v1/findings/{f['id']}/raise-risk").json()
    again = client.post(f"/api/v1/findings/{f['id']}/raise-risk").json()
    assert first["risk"] is not None and first["risk"] == again["risk"]
    risks = client.get("/api/v1/risks").json()
    titles = [r["title"] for r in (risks["items"] if isinstance(risks, dict) else risks)]
    assert titles.count("Finding F-001: A.5.1: Fail") == 1


def test_list_filters_and_summary(client, db, seeded, clock):
    who = people(db)
    as_(client, AUDITOR)
    _, items = audit_with_results(client)
    raise_finding(client, items["A.5.1"]["id"], owner_id=str(who["auditor"].id))
    raise_finding(client, items["A.5.2"]["id"], grade="observation")
    codes = lambda q="": [f["code"] for f in client.get(f"/api/v1/findings{q}").json()]  # noqa: E731
    assert codes() == ["F-001", "F-002"]
    assert codes("?owner=me") == ["F-001"]
    assert codes("?owner=none") == ["F-002"]
    assert codes("?grade=observation") == ["F-002"]
    assert codes("?overdue=true") == []
    clock.advance(days=31)
    as_(client, AUDITOR)
    assert codes("?overdue=true") == ["F-001"]
    summary = client.get("/api/v1/findings/summary").json()
    assert summary == {
        "open": 2,
        "overdue": 1,
        "by_grade": {"major": 1, "minor": 0, "observation": 1, "ofi": 0},
        "by_status": {"open": 2, "action_planned": 0, "awaiting_verification": 0, "closed": 0},
    }
