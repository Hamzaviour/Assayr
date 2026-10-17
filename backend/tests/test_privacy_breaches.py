from datetime import timedelta

from sqlalchemy import func, select

from assayr.risk.models import Risk
from tests.conftest import create_user, sign_in


def officer(client, db):
    create_user(db, "dpo@acme.com", roles=(("privacy_officer", None),), full_name="Dana DPO")
    sign_in(client, "dpo@acme.com")


def new(client, clock, **extra):
    body = {
        "title": "Invented email sent to wrong recipient",
        "discovered_at": clock.now.isoformat(),
        "data_categories": ["contact", "financial"],
        "people_affected": 40,
        "severity": "medium",
        **extra,
    }
    response = client.post("/api/v1/privacy/breaches", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_codes_and_the_72_hour_deadline(client, db, seeded, clock):
    officer(client, db)
    b = new(client, clock, regulator_notify="required")
    assert b["code"] == "PDB-001" and b["status"] == "open"
    deadline = (clock.now + timedelta(hours=72)).isoformat()[:16]
    assert b["notify_deadline"][:16] == deadline
    assert b["notification_overdue"] is False and 71 <= b["hours_left"] <= 72
    clock.advance(hours=73)
    sign_in(client, "dpo@acme.com")
    again = client.get(f"/api/v1/privacy/breaches/{b['id']}").json()
    assert again["notification_overdue"] is True


def test_no_countdown_when_notification_is_not_required(client, db, seeded, clock):
    officer(client, db)
    b = new(client, clock, regulator_notify="not_required", people_notify="not_required")
    clock.advance(hours=100)
    sign_in(client, "dpo@acme.com")
    again = client.get(f"/api/v1/privacy/breaches/{b['id']}").json()
    assert again["notification_overdue"] is False and again["hours_left"] is None


def test_recording_the_notifications_stops_the_clock(client, db, seeded, clock):
    officer(client, db)
    b = new(client, clock, regulator_notify="required", people_notify="required")
    url = f"/api/v1/privacy/breaches/{b['id']}"
    client.patch(url, json={"regulator_notified_at": clock.now.isoformat()})
    clock.advance(hours=80)
    sign_in(client, "dpo@acme.com")
    assert client.get(url).json()["notification_overdue"] is True  # people still not told
    client.patch(url, json={"people_notified_at": clock.now.isoformat(), "status": "contained"})
    after = client.get(url).json()
    assert after["notification_overdue"] is False and after["status"] == "contained"


def test_raise_a_risk_once(client, db, seeded, clock):
    officer(client, db)
    b = new(client, clock)
    first = client.post(f"/api/v1/privacy/breaches/{b['id']}/raise-risk").json()
    second = client.post(f"/api/v1/privacy/breaches/{b['id']}/raise-risk").json()
    assert first["risk"]["code"] == second["risk"]["code"]
    assert db.scalar(select(func.count()).select_from(Risk).where(Risk.category == "Privacy breach")) == 1


def test_validation(client, db, seeded, clock):
    officer(client, db)
    bad = client.post(
        "/api/v1/privacy/breaches",
        json={"title": "x", "discovered_at": clock.now.isoformat(), "severity": "apocalyptic"},
    )
    assert bad.status_code == 422


def test_breaches_are_hidden_from_people_without_sensitive_access(client, db, seeded, clock):
    officer(client, db)
    b = new(client, clock)
    create_user(db, "vera@acme.com", roles=(("viewer", None),), full_name="Vera")
    sign_in(client, "vera@acme.com")
    assert client.get("/api/v1/privacy/breaches").status_code == 403
    assert client.get(f"/api/v1/privacy/breaches/{b['id']}").status_code == 403
    assert client.get("/api/v1/privacy/summary").json()["breaches_open"] == 1
