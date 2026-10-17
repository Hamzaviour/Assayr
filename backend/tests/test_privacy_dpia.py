import pytest
from sqlalchemy import func, select

from assayr.privacy.dpia import dpia_recommended
from assayr.risk.models import Risk
from tests.conftest import create_user, sign_in


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def activity(client):
    return client.post(
        "/api/v1/privacy/activities", json={"name": "Clinic records", "lawful_basis": "legal_obligation"}
    ).json()


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        ({}, False),
        ({"large_scale": True}, False),
        ({"large_scale": True, "monitoring": True}, True),
        ({"sensitive": True}, True),
        ({"children": True}, True),
        ({"automated": True}, True),
        ({"new_tech": True, "sensitive": False}, False),
    ],
)
def test_recommendation(answers, expected):
    assert dpia_recommended(answers) is expected


def test_create_assess_submit_and_approve(client, db, seeded):
    manager(client, db)
    a = activity(client)
    url = f"/api/v1/privacy/activities/{a['id']}/dpia"
    assert client.get(url).status_code == 404
    body = client.put(
        url, json={"screening": {"sensitive": True}, "description": "Invented description"}
    ).json()
    assert body["status"] == "draft" and body["recommended"] is True
    risk = client.post(
        f"{url}/risks",
        json={
            "title": "Unauthorised access to records",
            "likelihood": 4,
            "impact": 5,
            "measures": "MFA",
            "residual_likelihood": 2,
            "residual_impact": 4,
        },
    ).json()
    assert risk["score"] == 20 and risk["level_label"] == "Very high" and risk["residual_score"] == 8
    assert client.post(f"{url}/submit").json()["status"] == "in_review"
    approved = client.post(f"{url}/approve").json()
    assert approved["status"] == "approved" and approved["approved_by"]["full_name"] == "Sana Malik"
    assert client.put(url, json={"description": "Change"}).status_code == 409
    reopened = client.post(f"{url}/reopen").json()
    assert reopened["status"] == "draft" and reopened["approved_by"] is None


def test_approval_needs_a_risk_or_a_conclusion(client, db, seeded):
    manager(client, db)
    a = activity(client)
    url = f"/api/v1/privacy/activities/{a['id']}/dpia"
    client.put(url, json={"screening": {}})
    assert client.post(f"{url}/approve").status_code == 409
    client.put(url, json={"conclusion": "Low residual risk; proceed."})
    assert client.post(f"{url}/approve").json()["status"] == "approved"


def test_ratings_are_validated(client, db, seeded):
    manager(client, db)
    a = activity(client)
    url = f"/api/v1/privacy/activities/{a['id']}/dpia"
    client.put(url, json={})
    assert client.post(f"{url}/risks", json={"title": "x", "likelihood": 7, "impact": 2}).status_code == 422
    assert client.put(url, json={"screening": {"unknown_q": True}}).status_code == 422


def test_raising_a_risk_creates_one_register_risk(client, db, seeded):
    manager(client, db)
    a = activity(client)
    url = f"/api/v1/privacy/activities/{a['id']}/dpia"
    client.put(url, json={})
    r = client.post(f"{url}/risks", json={"title": "Over-retention", "likelihood": 3, "impact": 3}).json()
    first = client.post(f"{url}/risks/{r['id']}/raise")
    assert first.status_code == 200, first.text
    second = client.post(f"{url}/risks/{r['id']}/raise").json()
    assert first.json()["risk"]["code"] == second["risk"]["code"]
    assert (
        db.scalar(select(func.count()).select_from(Risk).where(Risk.title == "Privacy: Over-retention")) == 1
    )


def test_viewers_read_but_cannot_edit(client, db, seeded):
    manager(client, db)
    a = activity(client)
    url = f"/api/v1/privacy/activities/{a['id']}/dpia"
    client.put(url, json={})
    create_user(db, "vera@acme.com", roles=(("viewer", None),), full_name="Vera")
    sign_in(client, "vera@acme.com")
    assert client.get(url).status_code == 200
    assert client.put(url, json={"description": "x"}).status_code == 403
