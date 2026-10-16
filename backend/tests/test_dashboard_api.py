from sqlalchemy import select

from assayr.catalogue.models import Control
from assayr.db import utcnow
from assayr.risk.models import Risk
from tests.conftest import create_user, sign_in
from tests.evidence_helpers import add_link
from tests.risk_helpers import new_risk


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def test_fresh_install_has_zeros_not_errors(client, db, seeded):
    manager(client, db)
    body = client.get("/api/v1/dashboard").json()
    iso = body["frameworks"][0]
    assert iso["total"] == 93 and iso["compliant"] == 0 and iso["readiness"] is None
    assert body["evidence"] == {"needs_attention": 0, "ok": 0, "total": 0}
    assert body["risks"]["total"] == 0 and body["unowned_controls"] == 93
    assert body["trend"] == []


def test_risk_buckets_include_closed_risks(client, db, seeded):
    manager(client, db)
    open_risk = new_risk(client, title="Open one")
    closing = new_risk(client, title="Closed one")
    risk = db.scalar(select(Risk).where(Risk.code == closing["code"]))
    risk.status, risk.closed_at = "closed", utcnow()
    db.commit()
    risks = client.get("/api/v1/dashboard").json()["risks"]
    assert (risks["open"], risks["in_progress"], risks["closed"], risks["total"]) == (1, 0, 1, 2)
    assert open_risk["status"] == "draft"


def test_evidence_attention_ignores_superseded(app, client, db, seeded):
    manager(client, db)
    control = db.scalar(select(Control).where(Control.code == "A.8.13"))
    for state in ("in_review", "rejected", "superseded", "accepted"):
        add_link(
            db,
            app.state.store,
            control.slots[0],
            scope_id=seeded.id,
            state=state,
            evidence_date=utcnow().date(),
            filename=f"{state}.pdf",
        )
    db.commit()
    assert client.get("/api/v1/dashboard").json()["evidence"] == {"needs_attention": 2, "ok": 1, "total": 3}


def test_without_risk_rights_the_risk_card_is_null(client, db, seeded, monkeypatch):
    # Every current role that reads controls also reads risks; simulate a future role that does not.
    from assayr.dashboard import router as dashboard_router
    from assayr.identity.rbac import Perm

    manager(client, db)
    monkeypatch.setattr(dashboard_router, "has_perm", lambda user, scope_id, perm: perm != Perm.RISKS_READ)
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200 and response.json()["risks"] is None


def test_framework_row_breaks_down_by_theme(client, db, seeded):
    manager(client, db)
    iso = client.get("/api/v1/dashboard").json()["frameworks"][0]
    groups = {g["name"]: g for g in iso["groups"]}
    assert set(groups) == {"Organizational", "People", "Physical", "Technological"}
    assert sum(g["total"] for g in groups.values()) == 93
    assert groups["People"] == {"name": "People", "total": 8, "compliant": 0, "readiness": None, "code": None}


def test_trend_keeps_the_last_snapshot_of_each_day(client, db, seeded):
    from datetime import timedelta

    from assayr.scoring.models import ScoreSnapshot

    manager(client, db)
    now = utcnow()
    for hours, value in ((-30, 5.0), (-2, 10.0), (-1, 12.0)):
        db.add(
            ScoreSnapshot(
                scope_id=seeded.id, taken_at=now + timedelta(hours=hours), readiness=value, status_counts={}
            )
        )
    db.commit()
    trend = client.get("/api/v1/dashboard").json()["trend"]
    dates = [p["date"] for p in trend]
    assert len(dates) == len(set(dates))
    assert trend[-1]["readiness"] == 12.0


def test_expired_and_expiring_accepted_evidence_needs_attention(app, client, db, seeded):
    from datetime import timedelta

    manager(client, db)
    control = db.scalar(select(Control).where(Control.code == "A.8.13"))
    today = utcnow().date()
    for days, name in ((-10, "expired"), (5, "expiring"), (200, "fresh")):
        link = add_link(
            db,
            app.state.store,
            control.slots[0],
            scope_id=seeded.id,
            state="accepted",
            evidence_date=today,
            filename=f"{name}.pdf",
        )
        link.expires_on = today + timedelta(days=days)
    db.commit()
    assert client.get("/api/v1/dashboard").json()["evidence"] == {"needs_attention": 2, "ok": 1, "total": 3}


def test_excluded_controls_are_not_counted(client, db, seeded):
    manager(client, db)
    controls = db.scalars(select(Control).where(Control.theme == "People")).all()
    for c in controls[:2]:
        c.status = "excluded"
    db.commit()
    body = client.get("/api/v1/dashboard").json()
    iso = body["frameworks"][0]
    assert iso["total"] == 91 and iso["excluded"] == 2
    people = next(g for g in iso["groups"] if g["name"] == "People")
    assert people["total"] == 6
    assert body["unowned_controls"] == 91
