from tests.conftest import create_user, sign_in


def login(client, db):
    create_user(db, "ana@acme.com")
    sign_in(client, "ana@acme.com")


def test_period_rules(client, db, seeded_all):
    login(client, db)
    bad = {"framework": "iso27001", "title": "x", "period_start": "2026-06-01", "period_end": "2026-01-01"}
    assert client.post("/api/v1/audits", json=bad).status_code == 422
    r = client.post("/api/v1/audits", json={"framework": "soc2", "title": "Type 2"})
    assert r.status_code == 422 and "observation period" in str(r.json()["detail"])
    a = client.post(
        "/api/v1/audits", json={"framework": "iso27001", "title": "ok", "period_start": "2026-01-01"}
    ).json()
    assert client.patch(f"/api/v1/audits/{a['id']}", json={"period_end": "2025-12-31"}).status_code == 422
    assert client.get(f"/api/v1/audits/{a['id']}").json()["period_end"] is None
    s = client.post(
        "/api/v1/audits",
        json={"framework": "soc2", "title": "T2", "period_start": "2026-01-01", "period_end": "2026-06-30"},
    ).json()
    assert client.patch(f"/api/v1/audits/{s['id']}", json={"period_end": None}).status_code == 422


def test_soc2_audit_rows_and_results(client, db, seeded_all):
    login(client, db)
    client.post(
        "/api/v1/soc2/activities", json={"code": "CC6.1.1", "title": "MFA", "test_procedure": "Inspected x."}
    )
    a = client.post(
        "/api/v1/audits",
        json={
            "framework": "soc2",
            "title": "Type 2 FY26",
            "period_start": "2026-01-01",
            "period_end": "2026-06-30",
        },
    ).json()
    client.post(f"/api/v1/audits/{a['id']}/items", json={"all": True})
    items = client.get(f"/api/v1/audits/{a['id']}").json()["items"]
    refs = [i["ref"] for i in items]
    assert "CC6.1.1" in refs and "CC6.1" not in refs and "CC6.2" in refs and len(refs) == 33
    item = next(i for i in items if i["ref"] == "CC6.1.1")
    assert item["assessment_area"] == "Inspected x." and item["sub_domain"] == "CC6.1"
    url = f"/api/v1/audits/{a['id']}/items/{item['id']}"
    assert client.patch(url, json={"result": "pass"}).status_code == 422
    assert client.patch(url, json={"result": "exception"}).status_code == 422  # note required
    r = client.patch(
        url,
        json={
            "result": "exception",
            "exception_note": "1 of 25 invented samples lacked approval",
            "sample_size": 25,
            "samples_tested": 25,
            "population": "Invented change tickets",
        },
    )
    assert r.status_code == 200 and r.json()["sample_size"] == 25
    assert client.patch(url, json={"samples_tested": 30}).status_code == 422
    assert client.patch(url, json={"exception_note": ""}).status_code == 422
    counts = client.get(f"/api/v1/audits/{a['id']}").json()["counts"]
    assert counts["exception"] == 1 and counts["tested"] == 1
    client.post(f"/api/v1/audits/{a['id']}/items", json={"refs": ["cc6.2"]})


def test_iso42001_audit(client, db, seeded_all):
    login(client, db)
    a = client.post("/api/v1/audits", json={"framework": "iso42001", "title": "AIMS audit"}).json()
    client.post(f"/api/v1/audits/{a['id']}/items", json={"refs": ["A.6.2.4", "6.1.4"]})
    items = client.get(f"/api/v1/audits/{a['id']}").json()["items"]
    assert [i["ref"] for i in items] == ["A.6.2.4", "6.1.4"]
    assert items[0]["domain"] == "AI system life cycle"
    url = f"/api/v1/audits/{a['id']}/items/{items[0]['id']}"
    assert client.patch(url, json={"result": "no_exception"}).status_code == 422
    assert client.patch(url, json={"result": "pass"}).status_code == 200
    assert client.get(f"/api/v1/audits/{a['id']}/export.xlsx").status_code == 200


def test_iso27001_audit_unchanged(client, db, seeded_all):
    login(client, db)
    a = client.post("/api/v1/audits", json={"framework": "iso27001", "title": "ISMS"}).json()
    client.post(f"/api/v1/audits/{a['id']}/items", json={"all": True})
    refs = [i["ref"] for i in client.get(f"/api/v1/audits/{a['id']}").json()["items"]]
    assert len(refs) == 93 and not any(r.startswith(("AI ", "CC")) for r in refs)
