from datetime import timedelta

from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from assayr.documents.models import DocumentControl
from tests.conftest import create_user, sign_in


def manager(client, db):
    user = create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")
    return user


def new_doc(client, **overrides):
    body = {"doc_type": "policy", "code": "POL-01", "title": "Information security policy"} | overrides
    return client.post("/api/v1/documents", json=body)


def upload(client, doc_id, data=b"%PDF-1.4 policy text", name="policy.pdf"):
    return client.post(f"/api/v1/documents/{doc_id}/file", files={"file": (name, data, "application/pdf")})


def test_create_draft_and_list_by_type(client, db, seeded):
    manager(client, db)
    response = new_doc(client)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "draft" and body["version_label"] == "1.0" and body["owner"]["full_name"]
    new_doc(client, doc_type="procedure", code="PRO-01", title="Access request procedure")
    rows = client.get("/api/v1/documents?type=procedure").json()
    assert [r["code"] for r in rows] == ["PRO-01"]
    assert [r["code"] for r in client.get("/api/v1/documents?q=access").json()] == ["PRO-01"]


def test_contributor_can_create_but_not_approve(client, db, seeded):
    create_user(db, "omar@acme.com", roles=(("contributor", None),), full_name="Omar Ali")
    sign_in(client, "omar@acme.com")
    doc = new_doc(client).json()
    assert doc["owner"]["full_name"] == "Omar Ali"
    assert client.post(f"/api/v1/documents/{doc['id']}/approve").status_code == 403


def test_viewer_cannot_create(client, db, seeded):
    create_user(db, "vera@acme.com", roles=(("viewer", None),), full_name="Vera")
    sign_in(client, "vera@acme.com")
    assert new_doc(client).status_code == 403


def test_duplicate_code_is_refused(client, db, seeded):
    manager(client, db)
    new_doc(client)
    response = new_doc(client, title="Another")
    assert response.status_code == 409
    assert response.json()["detail"] == "A document with the reference POL-01 already exists."


def test_approve_sets_review_date_and_is_audited(client, db, seeded, clock):
    manager(client, db)
    doc = new_doc(client).json()
    body = client.post(f"/api/v1/documents/{doc['id']}/approve").json()
    assert body["status"] == "approved" and body["approved_by"]["full_name"] == "Sana Malik"
    assert body["review_due"] == (clock.now.date() + timedelta(days=365)).isoformat()
    assert db.scalar(select(AuditLog).where(AuditLog.action == "document.approve")) is not None


def test_review_due_flag(client, db, seeded, clock):
    manager(client, db)
    doc = new_doc(client).json()
    client.post(f"/api/v1/documents/{doc['id']}/approve")
    clock.advance(days=366)
    sign_in(client, "sana@acme.com")
    row = client.get("/api/v1/documents").json()[0]
    assert row["review_overdue"] is True


def test_file_upload_and_download(client, db, seeded):
    manager(client, db)
    doc = new_doc(client).json()
    body = upload(client, doc["id"]).json()
    assert body["filename"] == "policy.pdf" and body["size"] == len(b"%PDF-1.4 policy text")
    download = client.get(f"/api/v1/documents/{doc['id']}/file")
    assert download.status_code == 200 and download.content == b"%PDF-1.4 policy text"


def test_new_file_on_approved_document_returns_it_to_draft(client, db, seeded):
    manager(client, db)
    doc = new_doc(client).json()
    upload(client, doc["id"])
    client.post(f"/api/v1/documents/{doc['id']}/approve")
    body = upload(client, doc["id"], data=b"%PDF-1.4 revised").json()
    assert body["status"] == "draft" and body["version_label"] == "1.1" and body["approved_by"] is None


def test_owner_edits_own_draft_but_not_others(client, db, seeded):
    create_user(db, "omar@acme.com", roles=(("contributor", None),), full_name="Omar Ali")
    create_user(db, "nadia@acme.com", roles=(("contributor", None),), full_name="Nadia")
    sign_in(client, "omar@acme.com")
    doc = new_doc(client).json()
    url = f"/api/v1/documents/{doc['id']}"
    assert client.patch(url, json={"title": "ISMS policy"}).json()["title"] == "ISMS policy"
    sign_in(client, "nadia@acme.com")
    assert client.patch(url, json={"title": "Hijack"}).status_code == 403


def test_link_controls_and_detail_lists_them(client, db, seeded):
    manager(client, db)
    doc = new_doc(client).json()
    url = f"/api/v1/documents/{doc['id']}/controls"
    assert client.put(url, json={"codes": ["A.5.1", "A.5.2"]}).status_code == 200
    detail = client.get(f"/api/v1/documents/{doc['id']}").json()
    assert sorted(c["code"] for c in detail["controls"]) == ["A.5.1", "A.5.2"]
    assert any(h["action"] == "document.create" for h in detail["history"])
    assert client.put(url, json={"codes": ["A.99.9"]}).status_code == 422


def test_deleting_a_control_removes_its_links(client, db, seeded):
    manager(client, db)
    doc = new_doc(client).json()
    client.put(f"/api/v1/documents/{doc['id']}/controls", json={"codes": ["A.5.1"]})
    db.delete(db.scalar(select(Control).where(Control.code == "A.5.1")))
    db.commit()
    assert db.scalars(select(DocumentControl)).all() == []


def test_control_documents_grouped_by_type(client, db, seeded):
    manager(client, db)
    pol = new_doc(client).json()
    pro = new_doc(client, doc_type="procedure", code="PRO-01", title="Access procedure").json()
    for doc in (pol, pro):
        client.put(f"/api/v1/documents/{doc['id']}/controls", json={"codes": ["A.5.15"]})
    body = client.get("/api/v1/controls/A.5.15/documents").json()
    assert [d["code"] for d in body["policy"]] == ["POL-01"]
    assert [d["code"] for d in body["procedure"]] == ["PRO-01"] and body["guideline"] == []
    assert set(body["policy"][0]) >= {"id", "code", "title", "status", "version_label", "review_due"}
    assert client.get("/api/v1/controls/A.5.1/documents").json()["policy"] == []
    assert client.get("/api/v1/controls/A.99.9/documents").status_code == 404


def test_link_and_unlink_from_the_control_page(client, db, seeded):
    manager(client, db)
    doc = new_doc(client).json()
    url = f"/api/v1/controls/A.5.1/documents/{doc['id']}"
    assert client.post(url).status_code == 200
    assert client.post(url).status_code == 200  # linking twice is harmless
    assert [d["code"] for d in client.get("/api/v1/controls/A.5.1/documents").json()["policy"]] == ["POL-01"]
    assert client.delete(url).status_code == 200
    assert client.get("/api/v1/controls/A.5.1/documents").json()["policy"] == []


def test_viewer_cannot_link_from_the_control_page(client, db, seeded):
    manager(client, db)
    doc = new_doc(client).json()
    create_user(db, "vera@acme.com", roles=(("viewer", None),), full_name="Vera")
    sign_in(client, "vera@acme.com")
    assert client.post(f"/api/v1/controls/A.5.1/documents/{doc['id']}").status_code == 403


def test_documents_link_to_nia_only_controls(client, db, seeded):
    from assayr.nia.seed import seed_nia

    seed_nia(db, seeded)
    db.commit()
    manager(client, db)
    doc = new_doc(client).json()
    assert (
        client.put(f"/api/v1/documents/{doc['id']}/controls", json={"codes": ["NIA AC 3"]}).status_code == 200
    )
    assert [d["code"] for d in client.get("/api/v1/controls/NIA AC 3/documents").json()["policy"]] == [
        "POL-01"
    ]


def test_approved_file_stays_downloadable_while_a_new_draft_is_pending(client, db, seeded):
    manager(client, db)
    doc = new_doc(client).json()
    upload(client, doc["id"], data=b"%PDF-1.4 approved text")
    client.post(f"/api/v1/documents/{doc['id']}/approve")
    body = upload(client, doc["id"], data=b"%PDF-1.4 revised").json()
    assert body["status"] == "draft" and body["approved_version"] == "1.0"
    approved = client.get(f"/api/v1/documents/{doc['id']}/file?approved=true")
    assert approved.content == b"%PDF-1.4 approved text"
    assert client.get(f"/api/v1/documents/{doc['id']}/file").content == b"%PDF-1.4 revised"
    rows = client.get("/api/v1/controls/A.5.1/documents").json()
    assert rows["policy"] == []  # not linked; shape check below
    client.put(f"/api/v1/documents/{doc['id']}/controls", json={"codes": ["A.5.1"]})
    assert client.get("/api/v1/controls/A.5.1/documents").json()["policy"][0]["approved_version"] == "1.0"
