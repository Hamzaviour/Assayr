import pytest
from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.nia.seed import seed_nia
from tests.conftest import create_user, sign_in


@pytest.fixture
def nia(db, seeded):
    seed_nia(db, seeded)
    db.commit()
    return seeded


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def auditor(client, db):
    create_user(db, "ali@acme.com", roles=(("internal_auditor", None),), full_name="Ali Auditor")
    sign_in(client, "ali@acme.com")


def new_audit(client, framework="nia-2.1", title="NIA internal audit 2026"):
    response = client.post("/api/v1/audits", json={"framework": framework, "title": title})
    assert response.status_code == 201, response.text
    return response.json()


def add(client, audit_id, body):
    return client.post(f"/api/v1/audits/{audit_id}/items", json=body)


def item(client, audit_id, ref):
    items = client.get(f"/api/v1/audits/{audit_id}").json()["items"]
    return next(i for i in items if i["ref"] == ref)


def test_create_and_list(client, db, nia):
    auditor(client, db)
    audit = new_audit(client)
    assert audit["status"] == "draft" and audit["counts"]["total"] == 0 and audit["can_write"] is True
    rows = client.get("/api/v1/audits").json()
    assert [r["title"] for r in rows] == ["NIA internal audit 2026"]
    bad = client.post("/api/v1/audits", json={"framework": "pci", "title": "x"})
    assert bad.status_code == 422


def test_add_all_controls_per_framework(client, db, nia):
    manager(client, db)
    iso = new_audit(client, "iso27001", "ISO internal audit")
    assert add(client, iso["id"], {"all": True}).json()["counts"]["total"] == 93
    refs = [i["ref"] for i in client.get(f"/api/v1/audits/{iso['id']}").json()["items"]]
    assert not any(r.startswith("NIA ") for r in refs)
    audit = new_audit(client)
    assert add(client, audit["id"], {"all": True}).json()["counts"]["total"] == 355
    su5 = item(client, audit["id"], "SU 5")
    assert su5["requirement"] in ("M", "A") and su5["domain"] == su5["sub_domain"] and su5["result"] is None


def test_adding_by_domain_then_all_creates_no_duplicates(client, db, nia):
    manager(client, db)
    audit = new_audit(client)
    assert add(client, audit["id"], {"domain": "PS"}).json()["counts"]["total"] == 12
    assert add(client, audit["id"], {"all": True}).json()["counts"]["total"] == 355


def test_refs_are_normalised_and_unknown_refs_refused(client, db, nia):
    manager(client, db)
    audit = new_audit(client)
    assert add(client, audit["id"], {"refs": ["su5", " su 7 "]}).json()["counts"]["total"] == 2
    bad = add(client, audit["id"], {"refs": ["ZZ 9"]})
    assert bad.status_code == 422 and "ZZ 9" in bad.json()["detail"]


def test_recording_a_result_starts_the_audit(client, db, nia):
    auditor(client, db)
    audit = new_audit(client)
    add(client, audit["id"], {"refs": ["SU 5"]})
    su5 = item(client, audit["id"], "SU 5")
    url = f"/api/v1/audits/{audit['id']}/items/{su5['id']}"
    body = client.patch(
        url, json={"result": "pass", "test_type": "OEA", "assessment_area": "Invented check"}
    ).json()
    assert body["result"] == "pass" and body["test_type"] == "OEA"
    detail = client.get(f"/api/v1/audits/{audit['id']}").json()
    assert (
        detail["status"] == "in_progress"
        and detail["counts"]["pass"] == 1
        and detail["counts"]["tested"] == 1
    )
    assert client.patch(url, json={"result": "maybe"}).status_code == 422


@pytest.mark.parametrize("role", ["control_owner", "viewer"])
def test_only_auditors_and_managers_record_results(client, db, nia, role):
    manager(client, db)
    audit = new_audit(client)
    add(client, audit["id"], {"refs": ["SU 5"]})
    su5 = item(client, audit["id"], "SU 5")
    create_user(db, "other@acme.com", roles=((role, None),), full_name="Other")
    sign_in(client, "other@acme.com")
    assert client.get(f"/api/v1/audits/{audit['id']}").json()["can_write"] is False
    assert (
        client.patch(f"/api/v1/audits/{audit['id']}/items/{su5['id']}", json={"result": "pass"}).status_code
        == 403
    )
    assert client.post("/api/v1/audits", json={"framework": "nia-2.1", "title": "x"}).status_code == 403


def test_complete_needs_every_control_tested(client, db, nia):
    auditor(client, db)
    audit = new_audit(client)
    url = f"/api/v1/audits/{audit['id']}/complete"
    empty = client.post(url)
    assert empty.status_code == 409 and "Add controls before completing" in empty.json()["detail"]
    add(client, audit["id"], {"refs": ["SU 5", "SU 7"]})
    su5 = item(client, audit["id"], "SU 5")
    client.patch(f"/api/v1/audits/{audit['id']}/items/{su5['id']}", json={"result": "pass"})
    untested = client.post(url)
    assert untested.status_code == 409 and "1 control" in untested.json()["detail"]
    su7 = item(client, audit["id"], "SU 7")
    client.patch(f"/api/v1/audits/{audit['id']}/items/{su7['id']}", json={"result": "partial"})
    done = client.post(url).json()
    assert done["status"] == "completed" and done["completed_by"]["full_name"] == "Ali Auditor"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "audit.complete")) is not None


def test_completed_audit_is_locked_until_a_manager_reopens_it(client, db, nia):
    auditor(client, db)
    audit = new_audit(client)
    add(client, audit["id"], {"refs": ["SU 5"]})
    su5 = item(client, audit["id"], "SU 5")
    item_url = f"/api/v1/audits/{audit['id']}/items/{su5['id']}"
    client.patch(item_url, json={"result": "pass"})
    client.post(f"/api/v1/audits/{audit['id']}/complete")
    locked = client.patch(item_url, json={"notes": "late change"})
    assert locked.status_code == 409
    assert locked.json()["detail"] == "This audit is completed. Reopen it to make changes."
    reopen = f"/api/v1/audits/{audit['id']}/reopen"
    assert client.post(reopen, json={"reason": "Missed evidence"}).status_code == 403
    manager(client, db)
    assert client.post(reopen, json={}).status_code == 422
    body = client.post(reopen, json={"reason": "Missed evidence"}).json()
    assert body["status"] == "in_progress"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "audit.reopen")) is not None


def test_items_can_be_removed_while_open(client, db, nia):
    manager(client, db)
    audit = new_audit(client)
    add(client, audit["id"], {"refs": ["SU 5", "SU 7"]})
    su5 = item(client, audit["id"], "SU 5")
    assert client.delete(f"/api/v1/audits/{audit['id']}/items/{su5['id']}").status_code == 200
    assert client.get(f"/api/v1/audits/{audit['id']}").json()["counts"]["total"] == 1


def test_audit_details_can_be_edited(client, db, nia):
    manager(client, db)
    audit = new_audit(client)
    body = client.patch(
        f"/api/v1/audits/{audit['id']}",
        json={"title": "NIA audit Q4", "period_start": "2026-10-01", "conclusion": "Invented conclusion"},
    ).json()
    assert body["title"] == "NIA audit Q4" and body["period_start"] == "2026-10-01"
