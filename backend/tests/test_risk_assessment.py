from datetime import timedelta

import pytest
from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from assayr.risk.service import derive_status
from tests.conftest import create_user, sign_in
from tests.risk_helpers import assessed_risk, new_risk, ratings


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def test_linked_controls_suggest_the_current_level(client, db, seeded, clock):
    manager(client, db)
    code = new_risk(client)["code"]
    client.put(f"/api/v1/risks/{code}/controls", json={"links": [{"code": "A.8.13"}, {"code": "A.8.7"}]})
    for control in db.scalars(select(Control).where(Control.code.in_(["A.8.13", "A.8.7"]))):
        control.status = "compliant"
    db.commit()
    body = client.patch(
        f"/api/v1/risks/{code}/assessment", json={"likelihood": 4, "consequence": ratings(3, operational=5)}
    ).json()
    assert body["draft"]["inherent"] == {
        "likelihood": 4,
        "consequence": 5,
        "score": 20,
        "band": "critical",
        "band_label": "Critical",
    }
    # Two compliant controls on likelihood: 4 → 2, so 2 × 5 = 10 (Medium).
    assert (body["draft"]["suggested"]["score"], body["draft"]["suggested"]["band"]) == (10, "medium")
    done = client.post(f"/api/v1/risks/{code}/assessment/finalize").json()
    assert (done["status"], done["draft"]) == ("assessed", None)
    assert (done["current"]["score"], done["target"]["score"]) == (10, 10)
    assert done["review_due"] == (clock().date() + timedelta(days=182)).isoformat()
    assert len(done["history"]) == 1 and done["latest"]["suggested"]["score"] == 10
    entry = db.scalar(select(AuditLog).where(AuditLog.action == "risk.assess"))
    assert entry.diff == {"inherent": 20, "current": 10, "target": 10, "band": "medium"}


def test_owner_needs_a_reason_to_override_the_suggestion(client, db, seeded, clock):
    manager(client, db)
    code = new_risk(client)["code"]
    url = f"/api/v1/risks/{code}/assessment"
    client.patch(url, json={"likelihood": 3, "consequence": ratings(3), "current_l": 2, "current_c": 3})
    response = client.post(f"{url}/finalize")
    assert response.status_code == 422
    assert response.json() == {"detail": "Explain why the current level differs from the suggested one."}
    client.patch(url, json={"current_reason": "Firewall rules were reviewed last month."})
    done = client.post(f"{url}/finalize").json()
    assert (
        done["current"]["score"] == 6
        and done["latest"]["current_reason"] == "Firewall rules were reviewed last month."
    )


@pytest.mark.parametrize(
    "body,message",
    [
        (
            {"likelihood": 3, "consequence": {"financial": 3}},
            "Rate the likelihood and every consequence area before finishing.",
        ),
        (
            {
                "likelihood": 2,
                "consequence": ratings(2),
                "current_l": 3,
                "current_c": 3,
                "current_reason": "x",
            },
            "The current level can't be higher than the inherent level.",
        ),
        (
            {"likelihood": 3, "consequence": ratings(3), "target_l": 4, "target_c": 4},
            "The target can't be worse than the current level.",
        ),
        (
            {"likelihood": 3, "consequence": ratings(3), "target_l": 2},
            "Give both the likelihood and the consequence for the target level.",
        ),
        (
            {"likelihood": 3, "consequence": ratings(3), "current_l": 2, "current_reason": "x"},
            "Give both the likelihood and the consequence for the current level.",
        ),
    ],
)
def test_finalize_validation(client, db, seeded, clock, body, message):
    manager(client, db)
    code = new_risk(client)["code"]
    assert client.patch(f"/api/v1/risks/{code}/assessment", json=body).status_code == 200
    response = client.post(f"/api/v1/risks/{code}/assessment/finalize")
    assert response.status_code == 422 and response.json() == {"detail": message}


def test_ratings_outside_the_scale_are_refused(client, db, seeded):
    manager(client, db)
    url = f"/api/v1/risks/{new_risk(client)['code']}/assessment"
    response = client.patch(url, json={"likelihood": 6})
    assert response.status_code == 422 and response.json() == {
        "detail": "Likelihood must be between 1 and 5."
    }
    response = client.patch(url, json={"consequence": {"weather": 2}})
    assert response.status_code == 422 and response.json() == {"detail": "Unknown consequence area: weather."}


def test_finalize_needs_an_open_assessment(client, db, seeded, clock):
    manager(client, db)
    risk = assessed_risk(client, likelihood=2, consequence=2)
    response = client.post(f"/api/v1/risks/{risk['code']}/assessment/finalize")
    assert response.status_code == 409 and response.json() == {"detail": "There's no assessment in progress."}


def test_reassessment_keeps_history(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=3, consequence=3)["code"]
    reopened = client.patch(f"/api/v1/risks/{code}/assessment", json={}).json()
    assert (reopened["status"], reopened["draft"]["likelihood"]) == ("reassessing", 3)
    clock.advance(minutes=5)
    client.patch(f"/api/v1/risks/{code}/assessment", json={"likelihood": 2})
    done = client.post(f"/api/v1/risks/{code}/assessment/finalize").json()
    assert (done["status"], done["current"]["score"], len(done["history"])) == ("assessed", 6, 2)
    assert done["history"][0]["current"]["score"] == 6 and done["history"][1]["current"]["score"] == 9


def test_only_editors_assess(client, db, seeded):
    manager(client, db)
    code = new_risk(client)["code"]
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    assert client.patch(f"/api/v1/risks/{code}/assessment", json={"likelihood": 2}).status_code == 403


BASE = dict(
    closed=False,
    has_final=True,
    has_draft=False,
    review_overdue=False,
    accepted=False,
    option=None,
    actions=[],
)


@pytest.mark.parametrize(
    "facts,expected",
    [
        ({"closed": True}, "closed"),
        ({"has_final": False, "has_draft": True}, "draft"),
        ({"has_draft": True}, "reassessing"),
        ({"review_overdue": True, "accepted": True}, "review_due"),
        ({"accepted": True, "option": "modify", "actions": ["todo"]}, "accepted"),
        ({"option": "retain"}, "treated"),
        ({"option": "share"}, "treated"),
        ({"option": "modify"}, "treatment_planned"),
        ({"option": "modify", "actions": ["todo", "in_progress"]}, "in_treatment"),
        ({"option": "modify", "actions": ["done", "cancelled"]}, "treated"),
        ({"option": "modify", "actions": ["cancelled"]}, "treatment_planned"),
        ({}, "assessed"),
    ],
)
def test_derive_status(facts, expected):
    assert derive_status(**{**BASE, **facts}) == expected
