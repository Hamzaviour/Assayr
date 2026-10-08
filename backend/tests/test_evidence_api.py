from datetime import timedelta

from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from tests.conftest import create_user, sign_in
from tests.evidence_helpers import policy_text, run_jobs
from tests.fixtures import make_pdf


def slot_url(db, code="A.5.1", index=0):
    control = db.scalar(select(Control).where(Control.code == code))
    return control, f"/api/v1/controls/{code}/slots/{control.slots[index].id}/artefacts"


def pdf_file(clock, name="policy.pdf"):
    return {"file": (name, make_pdf(policy_text(clock().date()).split("\n")), "application/pdf")}


def manager(client, db):
    user = create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")
    return user


def test_upload_then_verification_result(client, db, seeded, clock, app):
    manager(client, db)
    _, url = slot_url(db)
    response = client.post(url, files=pdf_file(clock))
    assert response.status_code == 202
    link = response.json()
    assert (link["state"], link["filename"], link["version_no"], link["uploaded_by"]) == (
        "verifying",
        "policy.pdf",
        1,
        "Sana Malik",
    )
    assert link["rules"] == [] and link["rules_planned"] > 0
    assert run_jobs(app) == 1
    done = client.get(f"/api/v1/artefact-links/{link['id']}").json()
    assert done["state"] == "accepted" and len(done["rules"]) == done["rules_planned"]
    assert "Information Security Policy" in done["text_preview"]
    assert (
        db.scalar(select(AuditLog).where(AuditLog.action == "evidence.upload")).diff["filename"]
        == "policy.pdf"
    )


def test_upload_filename_is_sanitised(client, db, seeded, clock):
    manager(client, db)
    _, url = slot_url(db)
    response = client.post(url, files=pdf_file(clock, name="..\\..\\evil<1>.pdf"))
    assert response.json()["filename"] == "evil1.pdf"


def test_upload_of_disguised_executable_is_rejected(client, db, seeded, app):
    manager(client, db)
    _, url = slot_url(db)
    link = client.post(
        url, files={"file": ("invoice.pdf", b"MZ\x90\x00 not a pdf", "application/pdf")}
    ).json()
    assert link["mime"] is None
    run_jobs(app)
    done = client.get(f"/api/v1/artefact-links/{link['id']}").json()
    assert done["state"] == "rejected"
    assert done["rules"][0]["code"] == "V-FMT" and done["rules"][0]["status"] == "fail"


def test_upload_over_the_size_limit_is_refused(app, client, db, seeded, clock):
    app.state.settings = app.state.settings.model_copy(update={"max_upload_mb": 0})
    manager(client, db)
    _, url = slot_url(db)
    response = client.post(url, files=pdf_file(clock))
    assert response.status_code == 413
    assert response.json() == {"detail": "The file is larger than the 0 MB limit."}
    assert [p for p in app.state.store.root.rglob("*") if p.is_file()] == []


def test_future_evidence_date_is_refused(client, db, seeded, clock):
    manager(client, db)
    _, url = slot_url(db)
    response = client.post(
        url, files=pdf_file(clock), data={"evidence_date": (clock().date() + timedelta(days=1)).isoformat()}
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "The evidence date can't be in the future."}


def test_control_owner_uploads_only_to_their_own_controls(client, db, seeded, clock):
    owner = create_user(db, "bilal@acme.com", roles=(("control_owner", None),))
    control, url = slot_url(db, "A.8.13")
    control.owner_id = owner.id
    db.commit()
    sign_in(client, "bilal@acme.com")
    assert client.post(url, files=pdf_file(clock)).status_code == 202
    _, other = slot_url(db, "A.5.1")
    assert client.post(other, files=pdf_file(clock)).status_code == 403


def test_slot_must_belong_to_the_control(client, db, seeded, clock):
    manager(client, db)
    a51, _ = slot_url(db, "A.5.1")
    wrong = f"/api/v1/controls/A.8.13/slots/{a51.slots[0].id}/artefacts"
    response = client.post(wrong, files=pdf_file(clock))
    assert response.status_code == 404 and response.json() == {"detail": "Evidence slot not found."}


def test_viewer_cannot_upload(client, db, seeded, clock):
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    _, url = slot_url(db)
    assert client.post(url, files=pdf_file(clock)).status_code == 403


def test_new_version_of_an_artefact(client, db, seeded, clock, app):
    manager(client, db)
    _, url = slot_url(db)
    first = client.post(url, files=pdf_file(clock)).json()
    second = client.post(
        url, files=pdf_file(clock, "policy-v2.pdf"), data={"artefact_id": first["artefact_id"]}
    ).json()
    assert (second["artefact_id"], second["version_no"]) == (first["artefact_id"], 2)


def test_download_is_an_attachment_and_is_audited(client, db, seeded, clock):
    manager(client, db)
    _, url = slot_url(db)
    link = client.post(url, files=pdf_file(clock)).json()
    response = client.get(f"/api/v1/artefact-versions/{link['version_id']}/download")
    assert response.status_code == 200 and response.content.startswith(b"%PDF-")
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "evidence.download")) is not None


def test_upload_requires_csrf(client, db, seeded, clock):
    manager(client, db)
    client.headers.pop("X-CSRF-Token")
    _, url = slot_url(db)
    assert client.post(url, files=pdf_file(clock)).status_code == 403


def test_a_file_that_failed_the_safety_checks_cannot_be_downloaded(client, db, seeded, app):
    manager(client, db)
    _, url = slot_url(db)
    link = client.post(
        url, files={"file": ("invoice.pdf", b"MZ\x90\x00 not a pdf", "application/pdf")}
    ).json()
    run_jobs(app)
    response = client.get(f"/api/v1/artefact-versions/{link['version_id']}/download")
    assert response.status_code == 403
    assert response.json() == {
        "detail": "This file failed the file-type or malware check, so it can't be downloaded."
    }
