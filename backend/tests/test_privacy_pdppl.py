import json
from pathlib import Path

from sqlalchemy import select

from assayr.catalogue.models import Control
from assayr.privacy.pdppl import OBLIGATIONS, PDPPL_FILE
from tests.conftest import create_user, sign_in


def officer(client, db):
    create_user(db, "dpo@acme.com", roles=(("privacy_officer", None),), full_name="Dana DPO")
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "dpo@acme.com")


def obligation(client, ref):
    rows = client.get("/api/v1/privacy/pdppl").json()["obligations"]
    return next(r for r in rows if r["ref"] == ref)


def test_the_data_file_is_our_own_summaries_mapped_to_real_controls(db, seeded):
    data = json.loads(Path(PDPPL_FILE).read_text(encoding="utf-8"))
    assert 25 <= len(data["obligations"]) <= 40
    assert "not legal advice" in data["notice"].lower()
    codes = set(db.scalars(select(Control.code)))
    for o in data["obligations"]:
        assert o["summary"] and o["topic"] and o["ref"].startswith("PDPPL-")
        assert set(o["iso"]) <= codes, o["ref"]
    assert len({o["ref"] for o in OBLIGATIONS}) == len(OBLIGATIONS)


def test_activity_consent_and_retention_fields(client, db, seeded, clock):
    officer(client, db)
    a = client.post(
        "/api/v1/privacy/activities",
        json={
            "name": "Newsletter",
            "lawful_basis": "consent",
            "consent_how": "Opt-in box on the form",
            "consent_withdrawal": "Unsubscribe link",
            "retention_review_due": str(clock.now.date()),
            "status": "active",
        },
    ).json()
    assert a["consent_how"] == "Opt-in box on the form" and a["retention_review_overdue"] is False
    clock.advance(days=1)
    sign_in(client, "dpo@acme.com")
    assert client.get(f"/api/v1/privacy/activities/{a['id']}").json()["retention_review_overdue"] is True


def test_records_obligation_needs_an_active_activity(client, db, seeded):
    officer(client, db)
    records = next(o["ref"] for o in OBLIGATIONS if "records" in o["evidence"])
    assert obligation(client, records)["evidence"]["result"] == "missing"
    client.post(
        "/api/v1/privacy/activities", json={"name": "Payroll", "lawful_basis": "contract", "status": "active"}
    )
    assert obligation(client, records)["evidence"]["result"] == "met"


def test_processor_obligation_ignores_ended_processors(client, db, seeded):
    officer(client, db)
    ref = next(o["ref"] for o in OBLIGATIONS if "processors" in o["evidence"])
    client.post(
        "/api/v1/privacy/processors", json={"name": "Old vendor", "dpa_signed": False, "status": "ended"}
    )
    assert obligation(client, ref)["evidence"]["result"] in ("met", "na")
    client.post("/api/v1/privacy/processors", json={"name": "PayCo", "dpa_signed": False})
    result = obligation(client, ref)["evidence"]
    assert result["result"] == "missing" and "PayCo" in result["reason"]
    client.post("/api/v1/privacy/processors", json={"name": "MailCo", "dpa_signed": True})
    assert obligation(client, ref)["evidence"]["result"] == "partial"


def test_overdue_requests_break_the_rights_obligation(client, db, seeded, clock):
    officer(client, db)
    ref = next(o["ref"] for o in OBLIGATIONS if "requests" in o["evidence"])
    client.post(
        "/api/v1/privacy/requests",
        json={"type": "access", "requester_name": "Invented", "received_on": "2020-01-01"},
    )
    result = obligation(client, ref)["evidence"]
    assert result["result"] == "missing" and "overdue" in result["reason"]


def test_privacy_officer_obligation(client, db, seeded):
    officer(client, db)
    ref = next(o["ref"] for o in OBLIGATIONS if "privacy_officer" in o["evidence"])
    assert obligation(client, ref)["evidence"]["result"] == "met"


def test_pdppl_summary_and_dashboard_row(client, db, seeded):
    officer(client, db)
    body = client.get("/api/v1/privacy/pdppl").json()
    assert body["total"] == len(OBLIGATIONS) and 0 <= body["compliant"] <= body["total"]
    assert {o["status"] for o in body["obligations"]} <= {
        "compliant",
        "in_progress",
        "in_review",
        "at_risk",
        "non_compliant",
        "not_started",
    }
    sign_in(client, "sana@acme.com")
    names = [f["name"] for f in client.get("/api/v1/dashboard").json()["frameworks"]]
    assert "PDPPL" in names


def test_summary_counts_dpia_and_processor_gaps(client, db, seeded):
    officer(client, db)
    a = client.post(
        "/api/v1/privacy/activities", json={"name": "Clinic", "lawful_basis": "legal_obligation"}
    ).json()
    client.put(f"/api/v1/privacy/activities/{a['id']}/dpia", json={"screening": {"sensitive": True}})
    client.post("/api/v1/privacy/processors", json={"name": "PayCo", "dpa_signed": False})
    summary = client.get("/api/v1/privacy/summary").json()
    assert summary["dpia_due"] == 1 and summary["processors_without_dpa"] == 1
