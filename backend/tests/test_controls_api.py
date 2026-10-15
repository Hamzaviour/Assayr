import uuid

from sqlalchemy import func, select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from assayr.identity.models import Scope
from tests.conftest import create_user, sign_in


def manager(client, db):
    user = create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")
    return user


def test_list_pages_through_all_93_controls(client, db, seeded):
    manager(client, db)
    first = client.get("/api/v1/controls").json()
    assert len(first["items"]) == 50 and first["next_cursor"] == 50
    assert first["items"][0]["code"] == "A.5.1"
    second = client.get("/api/v1/controls", params={"cursor": first["next_cursor"]}).json()
    assert len(second["items"]) == 43 and second["next_cursor"] is None


def test_filters_by_theme_and_search(client, db, seeded):
    manager(client, db)
    people = client.get("/api/v1/controls", params={"theme": "People", "limit": 200}).json()["items"]
    assert len(people) == 8
    backup = client.get("/api/v1/controls", params={"q": "BACKUP"}).json()["items"]
    assert [c["code"] for c in backup] == ["A.8.13"]


def test_search_treats_wildcards_literally(client, db, seeded):
    manager(client, db)
    assert client.get("/api/v1/controls", params={"q": "%"}).json()["items"] == []
    assert client.get("/api/v1/controls", params={"q": "_"}).json()["items"] == []


def test_owner_me_filter(client, db, seeded):
    user = manager(client, db)
    control = db.scalar(select(Control).where(Control.code == "A.5.15"))
    control.owner_id = user.id
    db.commit()
    items = client.get("/api/v1/controls", params={"owner": "me"}).json()["items"]
    assert [c["code"] for c in items] == ["A.5.15"]
    assert items[0]["owner"] == {"id": str(user.id), "full_name": "Sana Malik"}


def test_summary_counts_by_theme_and_status(client, db, seeded):
    manager(client, db)
    summary = client.get("/api/v1/controls/summary").json()
    assert summary["total"] == 93
    assert summary["by_theme"] == {"Organizational": 37, "People": 8, "Physical": 14, "Technological": 34}
    assert summary["by_status"] == {"not_started": 93}


def test_detail_includes_slots_and_requirements(client, db, seeded):
    manager(client, db)
    detail = client.get("/api/v1/controls/A.8.13").json()
    assert detail["title"] == "Information backup"
    assert len(detail["slots"]) == 3
    assert detail["requirements"] == [{"ref": "A.8.13", "title": "Information backup"}]
    assert client.get("/api/v1/controls/A.9.99").status_code == 404


def test_manager_updates_implementation_and_it_is_audited(client, db, seeded):
    manager(client, db)
    response = client.patch(
        "/api/v1/controls/A.8.13",
        json={
            "implementation_status": "partial",
            "implementation_text": "Nightly Veeam jobs; restore tests quarterly.",
        },
    )
    assert response.status_code == 200
    assert response.json()["implementation_status"] == "partial"
    entry = db.scalar(select(AuditLog).where(AuditLog.action == "control.update"))
    assert entry.entity_id == "A.8.13"
    assert entry.diff["implementation_status"] == ["not_started", "partial"]


def test_no_op_update_writes_no_audit_entry(client, db, seeded):
    manager(client, db)
    client.patch("/api/v1/controls/A.8.13", json={"implementation_status": "not_started"})
    assert (
        db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "control.update")) == 0
    )


def test_control_owner_can_edit_only_their_own_controls(client, db, seeded):
    owner = create_user(db, "bilal@acme.com", roles=(("control_owner", None),), full_name="Bilal Khan")
    own = db.scalar(select(Control).where(Control.code == "A.8.13"))
    own.owner_id = owner.id
    db.commit()
    sign_in(client, "bilal@acme.com")
    assert client.patch("/api/v1/controls/A.8.13", json={"implementation_text": "Mine."}).status_code == 200
    assert (
        client.patch("/api/v1/controls/A.5.1", json={"implementation_text": "Not mine."}).status_code == 403
    )
    response = client.patch("/api/v1/controls/A.8.13", json={"owner_id": None})
    assert response.status_code == 403
    assert response.json() == {"detail": "Only an ISMS manager can change the owner."}


def test_owner_must_be_an_active_user(client, db, seeded):
    manager(client, db)
    gone = create_user(db, "gone@acme.com", active=False)
    for owner_id in (str(uuid.uuid4()), str(gone.id)):
        response = client.patch("/api/v1/controls/A.8.13", json={"owner_id": owner_id})
        assert response.status_code == 422
        assert response.json() == {"detail": "Owner must be an active user."}


def test_scoped_user_cannot_read_another_scope(client, db, seeded):
    other_scope = uuid.uuid4()
    db.add(Scope(id=other_scope, organization_id=seeded.organization_id, name="Subsidiary"))
    db.commit()
    create_user(db, "aud@other.com", roles=(("viewer", other_scope),))
    sign_in(client, "aud@other.com")
    assert client.get("/api/v1/controls").status_code == 403
    assert client.get("/api/v1/controls", params={"scope_id": str(other_scope)}).json()["items"] == []


def test_patch_without_csrf_is_rejected(client, db, seeded):
    manager(client, db)
    client.headers.pop("X-CSRF-Token")
    assert client.patch("/api/v1/controls/A.8.13", json={"implementation_text": "x"}).status_code == 403


def test_frameworks_lists_iso27001(client, db, seeded):
    manager(client, db)
    frameworks = client.get("/api/v1/frameworks").json()
    assert frameworks[0]["code"] == "ISO27001:2022"
    assert frameworks[0]["requirement_count"] == 41 + 4 + 93


def test_owner_none_lists_unowned_controls(client, db, seeded):
    manager(client, db)
    page = client.get("/api/v1/controls?owner=none&limit=200").json()
    assert len(page["items"]) == 93
