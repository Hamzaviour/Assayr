from tests.conftest import create_user, sign_in


def test_rows_for_each_framework(client, db, seeded_all):
    create_user(db, "ana@acme.com")
    sign_in(client, "ana@acme.com")
    client.post("/api/v1/soc2/activities", json={"code": "CC6.1.1", "title": "Invented"})
    rows = client.get("/api/v1/dashboard").json()["frameworks"]
    codes = [r["code"] for r in rows]
    assert codes[0] == "ISO27001:2022" and codes[-1] == "pdppl-2016"
    assert codes.index("ISO42001:2023") < codes.index("SOC2:2017")
    iso = rows[0]
    assert iso["total"] == 93
    ai = next(r for r in rows if r["code"] == "ISO42001:2023")
    assert (ai["name"], ai["total"]) == ("ISO/IEC 42001", 70)
    assert "AI system life cycle" in {g["name"] for g in ai["groups"]}
    soc2 = next(r for r in rows if r["code"] == "SOC2:2017")
    assert (soc2["name"], soc2["total"]) == ("SOC 2", 33)  # criteria only; activities roll up
    assert len(soc2["groups"]) == 9


def test_no_rows_without_controls(client, db, seeded):
    create_user(db, "ana@acme.com")
    sign_in(client, "ana@acme.com")
    codes = [r["code"] for r in client.get("/api/v1/dashboard").json()["frameworks"]]
    assert "ISO42001:2023" not in codes and "SOC2:2017" not in codes
