from sqlalchemy import select

from assayr.catalogue.models import Control
from assayr.db import utcnow
from assayr.scoring.service import recompute_scope
from tests.conftest import create_user, sign_in
from tests.evidence_helpers import add_link


def a813(db):
    return db.scalar(select(Control).where(Control.code == "A.8.13"))


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def test_detail_shows_slot_states_and_latest_evidence(app, client, db, seeded):
    manager(client, db)
    detail = client.get("/api/v1/controls/A.8.13").json()
    assert [s["state"] for s in detail["slots"]] == ["missing", "missing", "missing"]
    assert detail["attestation"] is None and detail["score"] is None
    control = a813(db)
    add_link(
        db,
        app.state.store,
        control.slots[0],
        scope_id=seeded.id,
        evidence_date=utcnow().date(),
        filename="backup-policy.pdf",
    )
    db.commit()
    slot = client.get("/api/v1/controls/A.8.13").json()["slots"][0]
    assert slot["state"] == "verified" and slot["artefact"]["filename"] == "backup-policy.pdf"


def test_owner_attests_and_full_evidence_makes_the_control_compliant(app, client, db, seeded):
    owner = create_user(db, "bilal@acme.com", roles=(("control_owner", None),), full_name="Bilal Khan")
    control = a813(db)
    control.owner_id = owner.id
    for slot in control.slots:
        add_link(db, app.state.store, slot, scope_id=seeded.id, evidence_date=utcnow().date())
    db.commit()
    sign_in(client, "bilal@acme.com")
    response = client.post(
        "/api/v1/controls/A.8.13/attest", json={"statement": "Backups run nightly as described."}
    )
    assert response.status_code == 200
    detail = response.json()
    assert (detail["status"], detail["score"]) == ("compliant", 100.0)
    assert detail["attestation"]["by"] == "Bilal Khan"


def test_only_the_owner_or_a_manager_can_attest(app, client, db, seeded):
    create_user(db, "other@acme.com", roles=(("control_owner", None),))
    sign_in(client, "other@acme.com")
    response = client.post("/api/v1/controls/A.8.13/attest", json={"statement": "Not mine."})
    assert response.status_code == 403
    assert response.json() == {"detail": "Only the control owner or an ISMS manager can attest."}


def test_readiness_appears_once_evidence_exists(app, client, db, seeded):
    manager(client, db)
    empty = client.get("/api/v1/readiness").json()
    assert empty["readiness"] is None and empty["status_counts"] == {"not_started": 93}
    control = a813(db)
    add_link(db, app.state.store, control.slots[0], scope_id=seeded.id, evidence_date=utcnow().date())
    recompute_scope(db, seeded.id, utcnow(), app.state.settings)
    db.commit()
    body = client.get("/api/v1/readiness").json()
    assert body["readiness"] == round(30.0 / 93, 1)
    assert body["by_theme"]["Technological"] == round(30.0 / 34, 1)
    assert body["by_theme"]["People"] == 0.0
    assert len(body["trend"]) == 1 and body["status_counts"]["in_progress"] == 1
