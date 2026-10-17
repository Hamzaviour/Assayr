from datetime import timedelta

from sqlalchemy import func, select

from assayr.risk.models import Risk
from tests.conftest import create_user, sign_in

SECTIONS = {
    k: "Invented text"
    for k in (
        "intended_use",
        "affected",
        "individual_impacts",
        "societal_impacts",
        "fairness",
        "transparency",
        "oversight",
        "safety",
        "data_quality",
        "conclusion",
    )
}


def login(client, db):
    user = create_user(db, "ana@acme.com")
    sign_in(client, "ana@acme.com")
    return user


def system(client, lifecycle="deployed", **extra):
    body = {
        "name": "Scorer",
        "purpose": "Invented",
        "source": "in_house",
        "lifecycle": lifecycle,
        "risk_level": 4,
    }
    return client.post("/api/v1/ai/systems", json={**body, **extra}).json()


def approve(client, url):
    client.put(url, json=SECTIONS)
    client.post(f"{url}/impacts", json={"area": "safety", "description": "x", "likelihood": 1, "impact": 1})
    client.post(f"{url}/submit")
    return client.post(f"{url}/approve")


def test_assess_submit_approve_reopen(client, db, seeded_all):
    login(client, db)
    s = system(client)
    url = f"/api/v1/ai/systems/{s['id']}/assessment"
    assert client.get(url).status_code == 404
    first = client.put(url, json={"intended_use": "Invented"}).json()
    assert first["status"] == "draft" and "affected individuals and groups" in first["missing"]
    r = client.post(f"{url}/submit")
    assert r.status_code == 409 and "affected individuals and groups" in r.json()["detail"]
    client.put(url, json=SECTIONS)
    r = client.post(f"{url}/submit")
    assert r.status_code == 409 and "impact" in r.json()["detail"]
    imp = client.post(
        f"{url}/impacts",
        json={
            "area": "fairness",
            "description": "Bias against an invented group",
            "likelihood": 4,
            "impact": 4,
        },
    ).json()
    assert (imp["score"], imp["level"]) == (16, 4)
    assert client.post(f"{url}/approve").status_code == 409  # not in review yet
    assert client.post(f"{url}/submit").json()["status"] == "in_review"
    approved = client.post(f"{url}/approve").json()
    assert approved["status"] == "approved" and approved["approved_by"]["full_name"] == "Test User"
    assert approved["review_due"] is not None
    assert client.get(f"/api/v1/ai/systems/{s['id']}").json()["assessment_status"] == "approved"
    assert client.put(url, json={"conclusion": "changed"}).status_code == 409
    assert client.delete(f"/api/v1/ai/systems/{s['id']}").status_code == 409
    # Raising does not edit the assessment, so it is allowed while approved (as for DPIAs).
    a = client.post(f"{url}/impacts/{imp['id']}/raise").json()
    b = client.post(f"{url}/impacts/{imp['id']}/raise").json()
    assert a["risk_id"] == b["risk_id"] and a["risk_code"]
    assert db.scalar(select(func.count()).select_from(Risk)) == 1
    reopened = client.post(f"{url}/reopen").json()
    assert reopened["status"] == "draft" and reopened["approved_by"] is None
    assert client.delete(f"{url}/impacts/{imp['id']}").status_code == 200


def test_impact_validation_and_permissions(client, db, seeded_all):
    login(client, db)
    s = system(client)
    url = f"/api/v1/ai/systems/{s['id']}/assessment"
    client.put(url, json={})
    bad = {"area": "colour", "description": "x", "likelihood": 1, "impact": 1}
    assert client.post(f"{url}/impacts", json=bad).status_code == 422
    assert client.post(f"{url}/impacts", json={**bad, "area": "safety", "likelihood": 9}).status_code == 422
    create_user(db, "vi@acme.com", roles=(("viewer", None),))
    sign_in(client, "vi@acme.com")
    assert client.get(url).status_code == 200 and client.get(url).json()["can_edit"] is False
    assert client.put(url, json=SECTIONS).status_code == 403


def test_checks(client, db, seeded_all, clock):
    user = login(client, db)

    def check(code):
        return client.get(f"/api/v1/controls/{code}").json()["assayr_check"]

    assert check("AI A.5.3")["met"] is False  # no AI systems yet
    assert check("AI A.4.2")["met"] is False
    s = system(client)
    url = f"/api/v1/ai/systems/{s['id']}/assessment"
    assert check("AI A.4.2")["met"] is True and "1 AI system" in check("AI A.4.2")["reason"]
    assert check("AI A.5.3")["met"] is False and "AIS-001" in check("AI A.5.3")["reason"]
    approve(client, url)
    assert check("AI A.5.3")["met"] is True and check("AI 8.4")["met"] is True
    assert check("AI A.5.2")["met"] is True
    clock.advance(days=400)
    sign_in(client, "ana@acme.com")  # the old session has expired
    assert check("AI A.5.2")["met"] is False
    client.post(f"{url}/reopen")
    assert check("AI A.5.3")["met"] is False
    assert check("AI A.3.2")["met"] is False  # no owner
    client.patch(f"/api/v1/ai/systems/{s['id']}", json={"owner_id": str(user.id)})
    assert check("AI A.3.2")["met"] is True
    high = client.post(
        f"{url}/impacts", json={"area": "safety", "description": "High", "likelihood": 5, "impact": 4}
    ).json()
    assert check("AI 8.3")["met"] is False
    client.post(f"{url}/impacts/{high['id']}/raise")
    assert check("AI 8.3")["met"] is True
    assert check("A.5.1") is None and check("AI A.2.2") is None
    assert timedelta  # imported for clarity of the clock step
