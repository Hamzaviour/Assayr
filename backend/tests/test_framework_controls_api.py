from sqlalchemy import func, select

from assayr.catalogue.models import Control
from assayr.evidence.models import ArtefactLink
from tests.conftest import create_user, sign_in
from tests.evidence_helpers import add_link


def manager(client, db):
    create_user(db, "ana@acme.com")
    sign_in(client, "ana@acme.com")


def control(db, code):
    return db.scalar(select(Control).where(Control.code == code))


def evidence(db, app, scope, code, filename):
    c = control(db, code)
    link = add_link(db, app.state.store, c.slots[0], scope_id=scope.id, filename=filename)
    db.commit()
    return link.version_id


def test_list_by_framework(client, db, seeded_all):
    manager(client, db)
    items = client.get("/api/v1/controls?framework=iso42001&limit=200").json()["items"]
    assert len(items) == 70 and {i["framework"] for i in items} == {"iso42001"}
    assert next(i for i in items if i["code"] == "AI A.2.2")["ref"] == "A.2.2"
    assert client.get("/api/v1/controls/summary?framework=soc2").json()["total"] == 33
    assert client.get("/api/v1/controls/summary").json()["total"] == 93
    assert client.get("/api/v1/controls?framework=pci").status_code == 422
    detail = client.get("/api/v1/controls/AI A.2.2").json()
    assert (detail["framework"], detail["ref"], detail["test_procedure"]) == ("iso42001", "A.2.2", None)


def test_related_and_reuse(app, client, db, seeded_all):
    manager(client, db)
    version_id = evidence(db, app, seeded_all, "A.5.1", "policy.pdf")
    related = client.get("/api/v1/controls/AI A.2.2/related").json()
    iso = next(r for r in related if r["code"] == "A.5.1")
    assert iso["framework"] == "iso27001" and iso["evidence"][0]["linked"] is False
    assert iso["evidence"][0]["version_id"] == str(version_id)
    r = client.post("/api/v1/controls/AI A.2.2/reuse-evidence", json={"version_id": str(version_id)})
    assert r.status_code == 200
    again = client.get("/api/v1/controls/AI A.2.2/related").json()
    assert next(r for r in again if r["code"] == "A.5.1")["evidence"][0]["linked"] is True
    assert (
        client.post(
            "/api/v1/controls/AI A.2.2/reuse-evidence", json={"version_id": str(version_id)}
        ).status_code
        == 200
    )
    slot = control(db, "AI A.2.2").slots[0]
    assert (
        db.scalar(select(func.count()).select_from(ArtefactLink).where(ArtefactLink.slot_id == slot.id)) == 1
    )
    # the ISO side sees the 42001 and SOC 2 controls that map to it
    back = {r["code"] for r in client.get("/api/v1/controls/A.5.1/related").json()}
    assert {"AI A.2.2", "CC2.2", "CC5.3"} <= back


def test_soc2_activity_uses_its_criterion_mapping(app, client, db, seeded_all):
    manager(client, db)
    db.add(Control(scope_id=seeded_all.id, code="CC6.1.1", title="Invented", framework="soc2", sort_order=1))
    db.commit()
    assert "A.5.15" in {r["code"] for r in client.get("/api/v1/controls/CC6.1.1/related").json()}


def test_reuse_rejects_unrelated_or_unknown_version(app, client, db, seeded_all):
    manager(client, db)
    version_id = evidence(db, app, seeded_all, "A.8.7", "malware.pdf")  # A.8.7 is not mapped to A.2.2
    r = client.post("/api/v1/controls/AI A.2.2/reuse-evidence", json={"version_id": str(version_id)})
    assert r.status_code == 422
    r = client.post(
        "/api/v1/controls/AI A.2.2/reuse-evidence",
        json={"version_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 422


def test_reuse_needs_write_rights(app, client, db, seeded_all):
    version_id = evidence(db, app, seeded_all, "A.5.1", "policy.pdf")
    create_user(db, "vi@acme.com", roles=(("viewer", None),))
    sign_in(client, "vi@acme.com")
    r = client.post("/api/v1/controls/AI A.2.2/reuse-evidence", json={"version_id": str(version_id)})
    assert r.status_code == 403
