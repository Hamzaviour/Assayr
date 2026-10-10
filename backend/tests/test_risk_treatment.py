from datetime import timedelta

from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.scoring.jobs import enqueue_recompute_all
from tests.conftest import create_user, sign_in
from tests.evidence_helpers import run_jobs
from tests.risk_helpers import assessed_risk, new_risk

STATEMENT = {"statement": "The residual risk is accepted until the next review."}


def manager(client, db):
    user = create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")
    return user


def test_modify_treatment_moves_through_the_states(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=4, consequence=4)["code"]
    planned = client.post(
        f"/api/v1/risks/{code}/treatment", json={"option": "modify", "budget": "PKR 2m", "due": "2026-12-31"}
    ).json()
    assert planned["status"] == "treatment_planned" and planned["treatment"]["budget"] == "PKR 2m"
    response = client.post(f"/api/v1/risks/{code}/actions", json={"title": "Enable MFA for remote access"})
    assert response.status_code == 201
    action = response.json()["actions"][0]
    assert action["status"] == "todo" and response.json()["progress"] == {"done": 0, "total": 1}
    client.patch(f"/api/v1/tasks/{action['id']}", json={"status": "in_progress"})
    assert client.get(f"/api/v1/risks/{code}").json()["status"] == "in_treatment"
    assert (
        client.patch(f"/api/v1/tasks/{action['id']}", json={"status": "done"}).json()["done_at"] is not None
    )
    treated = client.get(f"/api/v1/risks/{code}").json()
    assert (treated["status"], treated["required_authority"], treated["can_accept"]) == (
        "treated",
        "isms_manager",
        True,
    )
    accepted = client.post(f"/api/v1/risks/{code}/accept", json=STATEMENT).json()
    assert accepted["status"] == "accepted" and accepted["can_accept"] is False
    assert accepted["acceptance"]["expires_at"][:10] == (clock().date() + timedelta(days=365)).isoformat()
    assert db.scalar(select(AuditLog).where(AuditLog.action == "risk.accept")).diff["band"] == "high"


def test_acceptance_needs_the_right_authority(client, db, seeded, clock):
    owner = create_user(db, "bilal@acme.com", roles=(("risk_owner", None),), full_name="Bilal Khan")
    create_user(db, "tariq@acme.com", roles=(("executive", None),), full_name="Tariq Qureshi")
    manager(client, db)
    high = assessed_risk(client, likelihood=4, consequence=4, owner_id=owner.id)["code"]
    critical = assessed_risk(client, likelihood=5, consequence=5, owner_id=owner.id)["code"]
    medium = assessed_risk(client, likelihood=3, consequence=3, owner_id=owner.id)["code"]
    response = client.post(f"/api/v1/risks/{critical}/accept", json=STATEMENT)
    assert response.status_code == 403
    assert response.json() == {"detail": "A critical risk must be accepted by top management."}
    sign_in(client, "bilal@acme.com")
    response = client.post(f"/api/v1/risks/{high}/accept", json=STATEMENT)
    assert response.status_code == 403
    assert response.json() == {"detail": "A high risk must be accepted by an ISMS manager."}
    assert client.get(f"/api/v1/risks/{high}").json()["can_accept"] is False
    assert client.post(f"/api/v1/risks/{medium}/accept", json=STATEMENT).json()["status"] == "accepted"
    sign_in(client, "tariq@acme.com")
    accepted = client.post(f"/api/v1/risks/{critical}/accept", json=STATEMENT).json()
    assert (accepted["acceptance"]["authority"], accepted["treatment"]["option"]) == ("executive", "retain")
    assert accepted["acceptance"]["expires_at"][:10] == (clock().date() + timedelta(days=90)).isoformat()


def test_risk_owner_cannot_accept_someone_elses_risk(client, db, seeded, clock):
    create_user(db, "bilal@acme.com", roles=(("risk_owner", None),))
    manager(client, db)
    code = assessed_risk(client, likelihood=2, consequence=2)["code"]
    sign_in(client, "bilal@acme.com")
    response = client.post(f"/api/v1/risks/{code}/accept", json=STATEMENT)
    assert response.status_code == 403
    assert response.json() == {"detail": "A low risk must be accepted by the risk owner."}


def test_acceptance_waits_for_open_actions(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=4, consequence=4)["code"]
    client.post(f"/api/v1/risks/{code}/treatment", json={"option": "modify"})
    client.post(f"/api/v1/risks/{code}/actions", json={"title": "Segment the network"})
    response = client.post(f"/api/v1/risks/{code}/accept", json=STATEMENT)
    assert response.status_code == 409
    assert response.json() == {"detail": "Finish the treatment actions before accepting the residual risk."}


def test_switching_treatment_does_not_skip_open_actions(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=4, consequence=4)["code"]
    client.post(f"/api/v1/risks/{code}/treatment", json={"option": "modify"})
    client.post(f"/api/v1/risks/{code}/actions", json={"title": "Segment the network"})
    response = client.post(f"/api/v1/risks/{code}/treatment", json={"option": "retain"})
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Finish or cancel the open treatment actions before changing the treatment."
    }
    assert client.get(f"/api/v1/risks/{code}").json()["treatment_option"] == "modify"


def test_actions_need_the_modify_option(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=3, consequence=3)["code"]
    response = client.post(f"/api/v1/risks/{code}/actions", json={"title": "x"})
    assert response.status_code == 409
    assert response.json() == {"detail": "Treatment actions belong to the 'modify' option. Choose it first."}


def test_avoid_and_share_need_a_record(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=3, consequence=3)["code"]
    response = client.post(f"/api/v1/risks/{code}/treatment", json={"option": "avoid"})
    assert response.status_code == 422 and response.json() == {
        "detail": "Record the decision to avoid the risk."
    }
    closed = client.post(
        f"/api/v1/risks/{code}/treatment",
        json={"option": "avoid", "note": "We stopped offering the service."},
    ).json()
    assert (closed["status"], closed["close_reason"]) == (
        "closed",
        "Avoided: We stopped offering the service.",
    )
    assert client.get("/api/v1/risks").json() == []
    assert [r["code"] for r in client.get("/api/v1/risks?include_closed=true").json()] == [code]
    other = assessed_risk(client, likelihood=3, consequence=3)["code"]
    response = client.post(f"/api/v1/risks/{other}/treatment", json={"option": "share"})
    assert response.status_code == 422
    assert response.json() == {"detail": "Record the contract or insurance that shares the risk."}


def test_treatment_needs_a_finished_assessment(client, db, seeded):
    manager(client, db)
    response = client.post(f"/api/v1/risks/{new_risk(client)['code']}/treatment", json={"option": "retain"})
    assert response.status_code == 409
    assert response.json() == {"detail": "Finish the assessment before choosing a treatment."}


def test_closing_a_risk(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=2, consequence=2)["code"]
    closed = client.post(f"/api/v1/risks/{code}/close", json={"reason": "The office was sold."}).json()
    assert (closed["status"], closed["can_edit"]) == ("closed", False)
    response = client.patch(f"/api/v1/risks/{code}", json={"title": "x"})
    assert response.status_code == 409 and response.json() == {"detail": "This risk is closed."}


def test_scheduled_check_flags_lapsed_acceptance(app, client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=2, consequence=2)["code"]
    client.post(f"/api/v1/risks/{code}/accept", json=STATEMENT)
    clock.advance(days=366)
    enqueue_recompute_all(db, clock())
    db.commit()
    run_jobs(app)
    sign_in(client, "sana@acme.com")
    assert client.get(f"/api/v1/risks/{code}").json()["status"] == "review_due"


def test_tasks_are_updated_by_assignees_and_risk_editors_only(client, db, seeded, clock):
    helper = create_user(db, "ali@acme.com", roles=(("contributor", None),), full_name="Ali Raza")
    create_user(db, "zara@acme.com", roles=(("contributor", None),))
    manager(client, db)
    code = assessed_risk(client, likelihood=4, consequence=4)["code"]
    client.post(f"/api/v1/risks/{code}/treatment", json={"option": "modify"})
    detail = client.post(
        f"/api/v1/risks/{code}/actions", json={"title": "Patch VPN", "assignee_id": str(helper.id)}
    ).json()
    task_id = detail["actions"][0]["id"]
    assert detail["actions"][0]["assignee"]["full_name"] == "Ali Raza"
    sign_in(client, "ali@acme.com")
    assert client.patch(f"/api/v1/tasks/{task_id}", json={"status": "in_progress"}).status_code == 200
    sign_in(client, "zara@acme.com")
    assert client.patch(f"/api/v1/tasks/{task_id}", json={"status": "done"}).status_code == 403
