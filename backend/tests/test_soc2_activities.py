from sqlalchemy import select

from assayr.catalogue.models import Control
from assayr.catalogue.soc2 import criterion_of, normalise_activity, refresh_criterion
from assayr.db import utcnow
from assayr.scoring.service import recompute_control
from tests.conftest import create_user, sign_in


def manager(client, db):
    create_user(db, "ana@acme.com")
    sign_in(client, "ana@acme.com")


def control(db, code):
    return db.scalar(select(Control).where(Control.code == code))


def test_normalise():
    assert normalise_activity(" cc 6.1.12 ") == "CC6.1.12"
    assert normalise_activity("CC6.1") is None and normalise_activity("A.5.1") is None
    assert normalise_activity("") is None and normalise_activity(None) is None
    assert criterion_of("CC6.1.12") == "CC6.1"


def test_add_and_edit_activity(client, db, seeded_all):
    manager(client, db)
    r = client.post(
        "/api/v1/soc2/activities",
        json={
            "code": "cc6.1.1",
            "title": "MFA for admin consoles",
            "test_procedure": "Inspected an invented config.",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert (body["code"], body["framework"], body["theme"]) == (
        "CC6.1.1",
        "soc2",
        "Logical and physical access controls",
    )
    assert body["test_procedure"] == "Inspected an invented config." and body["slots"]
    assert [q["ref"] for q in body["requirements"]] == ["CC6.1"]
    r = client.patch("/api/v1/soc2/activities/CC6.1.1", json={"test_procedure": "Inspected invented logs."})
    assert r.json()["test_procedure"] == "Inspected invented logs."
    codes = [c["code"] for c in client.get("/api/v1/controls?framework=soc2&limit=200").json()["items"]]
    assert codes.index("CC6.1") < codes.index("CC6.1.1") < codes.index("CC6.2")


def test_activity_errors(client, db, seeded_all):
    manager(client, db)
    client.post("/api/v1/soc2/activities", json={"code": "CC6.1.1", "title": "MFA"})
    assert client.post("/api/v1/soc2/activities", json={"code": "CC10.1.1", "title": "x"}).status_code == 422
    assert client.post("/api/v1/soc2/activities", json={"code": "A.5.1", "title": "x"}).status_code == 422
    assert client.post("/api/v1/soc2/activities", json={"code": "CC6.1.1", "title": "dup"}).status_code == 409
    assert client.patch("/api/v1/soc2/activities/CC6.1.9", json={"title": "x"}).status_code == 404
    assert client.patch("/api/v1/soc2/activities/CC6.1", json={"title": "x"}).status_code == 404


def test_only_writers_add(client, db, seeded_all):
    create_user(db, "vi@acme.com", roles=(("viewer", None),))
    sign_in(client, "vi@acme.com")
    assert client.post("/api/v1/soc2/activities", json={"code": "CC6.1.1", "title": "x"}).status_code == 403


def test_criterion_status_follows_activities(client, db, seeded_all, settings):
    manager(client, db)
    for code in ("CC6.1.1", "CC6.1.2"):
        client.post("/api/v1/soc2/activities", json={"code": code, "title": "Invented"})
    db.expire_all()
    a, b = control(db, "CC6.1.1"), control(db, "CC6.1.2")
    a.status, b.status = "compliant", "in_progress"
    refresh_criterion(db, seeded_all.id, "CC6.1", utcnow())
    assert control(db, "CC6.1").status == "in_progress"
    b.status = "non_compliant"
    refresh_criterion(db, seeded_all.id, "CC6.1", utcnow())
    assert control(db, "CC6.1").status == "non_compliant"
    b.applicable = False
    b.status = "excluded"
    refresh_criterion(db, seeded_all.id, "CC6.1", utcnow())
    assert control(db, "CC6.1").status == "compliant"
    # recomputing an activity rolls its criterion up too
    a.implementation_status = "partial"
    recompute_control(db, a, utcnow(), settings, "test")
    assert control(db, "CC6.1").status == a.status == "in_progress"
    # recomputing the criterion itself keeps the roll-up instead of its own evidence
    recompute_control(db, control(db, "CC6.1"), utcnow(), settings, "test")
    assert control(db, "CC6.1").status == "in_progress"
