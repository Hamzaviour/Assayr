from sqlalchemy import func, select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from assayr.db import utcnow
from assayr.risk.models import RiskTemplate, Threat, Vulnerability
from assayr.risk.seed import LibraryResult, ensure_methodology, ensure_risk_library
from tests.conftest import create_user, sign_in

DIMENSIONS = {"financial", "operational", "legal", "reputation", "data"}


def test_seeded_library_is_complete_and_consistent(db, seeded):
    assert db.scalar(select(func.count()).select_from(Threat)) == 40
    assert db.scalar(select(func.count()).select_from(Vulnerability)) == 60
    assert db.scalar(select(func.count()).select_from(RiskTemplate)) == 25
    threats = set(db.scalars(select(Threat.code)))
    vulnerabilities = set(db.scalars(select(Vulnerability.code)))
    controls = set(db.scalars(select(Control.code)))
    for template in db.scalars(select(RiskTemplate)):
        assert set(template.threat_codes) <= threats, template.code
        assert set(template.vulnerability_codes) <= vulnerabilities, template.code
        assert set(template.control_codes) <= controls, template.code
        assert set(template.consequence) == DIMENSIONS, template.code
        assert 1 <= template.likelihood <= 5


def test_seeding_twice_adds_nothing(db, seeded):
    assert ensure_risk_library(db) == LibraryResult()
    assert ensure_methodology(db, utcnow()).version_no == 1


def test_methodology_api(client, db, seeded):
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    body = client.get("/api/v1/risk-methodology").json()
    assert body["version_no"] == 1
    assert [b["key"] for b in body["bands"]] == ["very_low", "low", "medium", "high", "critical"]
    assert body["likelihood"][3]["label"] == "Likely"
    assert len(body["consequence"]["dimensions"]) == 5


def test_library_api_and_custom_entries(client, db, seeded):
    create_user(db, "sana@acme.com")
    sign_in(client, "sana@acme.com")
    library = client.get("/api/v1/risk-library").json()
    assert library["threats"][0]["code"] == "T01" and len(library["templates"]) == 25
    created = client.post(
        "/api/v1/risk-library/threats", json={"name": "Drone surveillance", "category": "Physical"}
    )
    assert created.status_code == 201
    assert (created.json()["code"], created.json()["is_custom"]) == ("T41", True)
    vulnerability = client.post(
        "/api/v1/risk-library/vulnerabilities",
        json={"name": "No CCTV on the loading bay", "category": "Physical"},
    ).json()
    assert vulnerability["code"] == "V61"
    assert (
        db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "risk_library.add"))
        == 2
    )


def test_only_risk_managers_extend_the_library(client, db, seeded):
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    response = client.post("/api/v1/risk-library/threats", json={"name": "x", "category": "y"})
    assert response.status_code == 403
