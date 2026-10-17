from tests.findings_helpers import AUDITOR, as_, audit_with_results, people, raise_finding


def test_bulk_raise_creates_one_finding_per_failed_row(client, db, seeded):
    people(db)
    as_(client, AUDITOR)
    audit, items = audit_with_results(client)
    url = f"/api/v1/audits/{audit['id']}/findings"
    first = client.post(url, json={"all": True})
    assert first.status_code == 200, first.text
    assert [f["ref"] for f in first.json()["created"]] == ["A.5.1", "A.5.2"] and first.json()["existing"] == 0
    again = client.post(url, json={"all": True}).json()
    assert again == {"created": [], "existing": 2}
    assert len(client.get("/api/v1/findings").json()) == 2


def test_bulk_raise_for_chosen_rows(client, db, seeded):
    people(db)
    as_(client, AUDITOR)
    audit, items = audit_with_results(client)
    url = f"/api/v1/audits/{audit['id']}/findings"
    one = client.post(url, json={"item_ids": [items["A.5.2"]["id"]]}).json()
    assert [f["ref"] for f in one["created"]] == ["A.5.2"]
    bad = client.post(url, json={"item_ids": [items["A.5.3"]["id"]]})
    assert bad.status_code == 422
    assert client.post(url, json={}).status_code == 422


def test_audit_rows_show_their_finding(client, db, seeded):
    people(db)
    as_(client, AUDITOR)
    audit, items = audit_with_results(client)
    f = raise_finding(client, items["A.5.1"]["id"])
    rows = {i["ref"]: i for i in client.get(f"/api/v1/audits/{audit['id']}").json()["items"]}
    assert rows["A.5.1"]["finding"] == {"id": f["id"], "code": "F-001", "status": "open"}
    assert rows["A.5.1"]["result_changed"] is False and rows["A.5.2"]["finding"] is None
    client.patch(f"/api/v1/audits/{audit['id']}/items/{items['A.5.1']['id']}", json={"result": "pass"})
    rows = {i["ref"]: i for i in client.get(f"/api/v1/audits/{audit['id']}").json()["items"]}
    assert rows["A.5.1"]["result_changed"] is True
    assert client.get(f"/api/v1/findings/{f['id']}").status_code == 200


def test_findings_outlive_their_audit_row(client, db, seeded):
    people(db)
    as_(client, AUDITOR)
    audit, items = audit_with_results(client)
    f = raise_finding(client, items["A.5.1"]["id"])
    assert client.delete(f"/api/v1/audits/{audit['id']}/items/{items['A.5.1']['id']}").status_code == 200
    kept = client.get(f"/api/v1/findings/{f['id']}").json()
    assert (kept["ref"], kept["framework"], kept["audit_item_id"]) == ("A.5.1", "iso27001", None)


def test_soc2_exceptions_become_minor_findings(client, db, seeded_all):
    people(db)
    as_(client, AUDITOR)
    audit, items = audit_with_results(client, "soc2", {"CC6.1": "exception", "CC6.2": "no_exception"})
    created = client.post(f"/api/v1/audits/{audit['id']}/findings", json={"all": True}).json()["created"]
    assert [(f["ref"], f["grade"], f["title"]) for f in created] == [("CC6.1", "minor", "CC6.1: Exception")]
    detail = client.get(f"/api/v1/findings/{created[0]['id']}").json()
    assert detail["description"] == "Invented exception"


def test_people_without_findings_rights_can_not_raise(client, db, seeded):
    people(db)
    as_(client, AUDITOR)
    audit, _ = audit_with_results(client)
    as_(client, "omar@acme.com")
    assert client.post(f"/api/v1/audits/{audit['id']}/findings", json={"all": True}).status_code == 403
