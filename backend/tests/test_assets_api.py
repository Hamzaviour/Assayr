from sqlalchemy import select

from assayr.audit.models import AuditLog
from tests.conftest import create_user, sign_in


def manager(client, db):
    user = create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")
    return user


def test_create_and_list_assets(client, db, seeded):
    manager(client, db)
    created = client.post(
        "/api/v1/assets",
        json={
            "name": "Core banking database",
            "type": "information",
            "classification": "restricted",
            "confidentiality": 5,
            "integrity": 5,
            "availability": 4,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert (body["code"], body["criticality"], body["lifecycle"]) == ("AST-001", 5, "in_use")
    client.post("/api/v1/assets", json={"name": "Email", "type": "cloud_service"})
    assert [a["code"] for a in client.get("/api/v1/assets").json()] == ["AST-001", "AST-002"]
    assert [a["name"] for a in client.get("/api/v1/assets?q=bank").json()] == ["Core banking database"]
    assert [a["name"] for a in client.get("/api/v1/assets?type=cloud_service").json()] == ["Email"]


def test_retired_assets_are_hidden_unless_asked(client, db, seeded):
    manager(client, db)
    asset = client.post("/api/v1/assets", json={"name": "Old file server", "type": "server"}).json()
    client.patch(f"/api/v1/assets/{asset['id']}", json={"lifecycle": "retired"})
    assert client.get("/api/v1/assets").json() == []
    assert len(client.get("/api/v1/assets?include_retired=true").json()) == 1


def test_control_owner_edits_only_their_own_assets(client, db, seeded):
    owner = create_user(db, "bilal@acme.com", roles=(("control_owner", None),), full_name="Bilal Khan")
    boss = manager(client, db)
    mine = client.post(
        "/api/v1/assets", json={"name": "Laptop fleet", "type": "endpoint", "owner_id": str(owner.id)}
    ).json()
    other = client.post("/api/v1/assets", json={"name": "Firewall", "type": "network_device"}).json()
    sign_in(client, "bilal@acme.com")
    assert client.patch(f"/api/v1/assets/{mine['id']}", json={"location": "Head office"}).json()[
        "location"
    ] == ("Head office")
    assert client.patch(f"/api/v1/assets/{other['id']}", json={"location": "x"}).status_code == 403
    response = client.patch(f"/api/v1/assets/{mine['id']}", json={"owner_id": str(boss.id)})
    assert response.status_code == 403
    assert response.json() == {"detail": "Only an ISMS manager can change the owner."}
    assert client.post("/api/v1/assets", json={"name": "x", "type": "server"}).status_code == 403


def test_owner_must_be_active_and_values_valid(client, db, seeded):
    gone = create_user(db, "gone@acme.com", active=False)
    manager(client, db)
    response = client.post("/api/v1/assets", json={"name": "x", "type": "server", "owner_id": str(gone.id)})
    assert response.status_code == 422 and response.json() == {"detail": "Owner must be an active user."}
    assert (
        client.post("/api/v1/assets", json={"name": "x", "type": "server", "confidentiality": 6}).status_code
        == 422
    )
    assert client.post("/api/v1/assets", json={"name": "x", "type": "spaceship"}).status_code == 422
    asset = client.post("/api/v1/assets", json={"name": "x", "type": "server"}).json()
    response = client.patch(f"/api/v1/assets/{asset['id']}", json={"name": None})
    assert response.status_code == 422 and response.json() == {"detail": "Name can't be empty."}


def test_asset_changes_are_audited(client, db, seeded):
    manager(client, db)
    asset = client.post("/api/v1/assets", json={"name": "HR system", "type": "application"}).json()
    client.patch(f"/api/v1/assets/{asset['id']}", json={"classification": "confidential"})
    actions = [e.action for e in db.scalars(select(AuditLog).where(AuditLog.entity_type == "asset"))]
    assert actions == ["asset.create", "asset.update"]
    update = db.scalar(select(AuditLog).where(AuditLog.action == "asset.update"))
    assert update.diff == {"classification": ["internal", "confidential"]}
