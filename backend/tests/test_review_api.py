from fastapi.testclient import TestClient
from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from tests.conftest import create_user, sign_in
from tests.evidence_helpers import policy_text, run_jobs
from tests.fixtures import PNG_BYTES, make_pdf


def screenshot_in_review(app, db, uploader_email="bilal@acme.com", file=("shot.png", PNG_BYTES, "image/png")):
    """Upload a file (a screenshot always lands in review) as a manager and return the link id."""
    create_user(db, uploader_email, full_name="Bilal Khan")
    control = db.scalar(select(Control).where(Control.code == "A.5.1"))
    with TestClient(app) as uploader:
        sign_in(uploader, uploader_email)
        url = f"/api/v1/controls/A.5.1/slots/{control.slots[0].id}/artefacts"
        link = uploader.post(url, files={"file": file}).json()
    run_jobs(app)
    return link["id"]


def reviewer(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def test_queue_lists_items_waiting_for_review(app, client, db, seeded):
    link_id = screenshot_in_review(app, db)
    reviewer(client, db)
    queue = client.get("/api/v1/review-queue").json()
    assert [(i["link_id"], i["control_code"], i["uploaded_by"]) for i in queue] == [
        (link_id, "A.5.1", "Bilal Khan")
    ]


def test_accepting_with_a_reason_updates_the_control(app, client, db, seeded):
    link_id = screenshot_in_review(app, db)
    reviewer(client, db)
    response = client.post(
        f"/api/v1/artefact-links/{link_id}/decision",
        json={"decision": "accept", "reason": "Screenshot shows the approved policy page."},
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["state"], body["decided_by"]) == ("accepted", "Sana Malik")
    assert client.get("/api/v1/review-queue").json() == []
    entry = db.scalar(select(AuditLog).where(AuditLog.action == "evidence.decision"))
    assert entry.diff["state"] == ["in_review", "accepted"]


def test_uploader_cannot_review_their_own_evidence(app, client, db, seeded):
    link_id = screenshot_in_review(app, db, uploader_email="sana@acme.com")
    sign_in(client, "sana@acme.com")
    response = client.post(
        f"/api/v1/artefact-links/{link_id}/decision", json={"decision": "accept", "reason": "ok"}
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "You can't review evidence you uploaded. Ask another reviewer."}


def test_reject_needs_a_reason(app, client, db, seeded):
    link_id = screenshot_in_review(app, db)
    reviewer(client, db)
    response = client.post(f"/api/v1/artefact-links/{link_id}/decision", json={"decision": "reject"})
    assert response.status_code == 422
    assert response.json() == {"detail": "Give a reason so the uploader knows what to fix."}


def test_accepting_evidence_no_check_could_read_needs_a_reason(app, client, db, seeded):
    link_id = screenshot_in_review(app, db)
    reviewer(client, db)
    response = client.post(f"/api/v1/artefact-links/{link_id}/decision", json={"decision": "accept"})
    assert response.status_code == 422
    assert response.json() == {
        "detail": "None of the content checks could run on this file. Say what you checked."
    }


def test_accepting_evidence_with_failed_checks_needs_a_reason(app, client, db, seeded, clock):
    draft = make_pdf(policy_text(clock().date(), approved=False).split("\n"))
    link_id = screenshot_in_review(app, db, file=("draft.pdf", draft, "application/pdf"))
    reviewer(client, db)
    response = client.post(f"/api/v1/artefact-links/{link_id}/decision", json={"decision": "accept"})
    assert response.status_code == 422
    assert response.json() == {
        "detail": "Some checks failed or raised warnings. Give a reason for accepting anyway."
    }


def test_final_decisions_cannot_be_repeated(app, client, db, seeded):
    link_id = screenshot_in_review(app, db)
    reviewer(client, db)
    url = f"/api/v1/artefact-links/{link_id}/decision"
    client.post(url, json={"decision": "accept", "reason": "ok"})
    response = client.post(url, json={"decision": "reject", "reason": "changed my mind"})
    assert response.status_code == 409


def test_reviewing_needs_the_reviewer_permission(app, client, db, seeded):
    link_id = screenshot_in_review(app, db)
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    assert client.get("/api/v1/review-queue").status_code == 403
    url = f"/api/v1/artefact-links/{link_id}/decision"
    assert client.post(url, json={"decision": "accept", "reason": "x"}).status_code == 403


def test_a_file_that_failed_the_safety_checks_cannot_be_accepted(app, client, db, seeded):
    link_id = screenshot_in_review(app, db, file=("invoice.pdf", b"MZ\x90\x00 not a pdf", "application/pdf"))
    reviewer(client, db)
    response = client.post(
        f"/api/v1/artefact-links/{link_id}/decision", json={"decision": "accept", "reason": "Looks fine"}
    )
    assert response.status_code == 422
    assert response.json() == {
        "detail": "This file failed the file-type or malware check and can't be accepted. Ask for a new upload."
    }
