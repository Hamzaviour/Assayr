"""Shared set-up for findings tests: an ISO audit with fail, partial and pass rows, and the people involved."""

from tests.conftest import create_user, sign_in

MANAGER = "sana@acme.com"
AUDITOR = "ali@acme.com"
OWNER = "omar@acme.com"
DOER = "dina@acme.com"


def people(db) -> dict:
    return {
        "manager": create_user(db, MANAGER, full_name="Sana Manager"),
        "auditor": create_user(db, AUDITOR, roles=(("internal_auditor", None),), full_name="Ali Auditor"),
        "owner": create_user(db, OWNER, roles=(("control_owner", None),), full_name="Omar Owner"),
        "doer": create_user(db, DOER, roles=(("control_owner", None),), full_name="Dina Doer"),
    }


def as_(client, email: str) -> None:
    client.cookies.clear()
    sign_in(client, email)


def audit_with_results(client, framework="iso27001", results=None) -> tuple[dict, dict[str, dict]]:
    """Creates an audit as the signed-in person and records results; returns the audit and its items by ref."""
    results = results or {"A.5.1": "fail", "A.5.2": "partial", "A.5.3": "pass"}
    body = {"framework": framework, "title": "Invented internal audit"}
    if framework == "soc2":
        body |= {"period_start": "2026-01-01", "period_end": "2026-06-30"}
    audit = client.post("/api/v1/audits", json=body).json()
    r = client.post(f"/api/v1/audits/{audit['id']}/items", json={"refs": list(results)})
    assert r.status_code == 200, r.text
    items = {i["ref"]: i for i in client.get(f"/api/v1/audits/{audit['id']}").json()["items"]}
    for ref, result in results.items():
        change = {"result": result}
        if result == "exception":
            change["exception_note"] = "Invented exception"
        r = client.patch(f"/api/v1/audits/{audit['id']}/items/{items[ref]['id']}", json=change)
        assert r.status_code == 200, r.text
    items = {i["ref"]: i for i in client.get(f"/api/v1/audits/{audit['id']}").json()["items"]}
    return audit, items


def raise_finding(client, item_id: str, **extra) -> dict:
    r = client.post("/api/v1/findings", json={"audit_item_id": item_id, **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()
