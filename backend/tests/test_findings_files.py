import io

from openpyxl import load_workbook

from assayr.verification.av import AvResult
from tests.findings_helpers import AUDITOR, DOER, as_, audit_with_results, people, raise_finding


def setup_action(client, db):
    who = people(db)
    as_(client, AUDITOR)
    _, items = audit_with_results(client)
    f = raise_finding(client, items["A.5.1"]["id"], owner_id=str(who["owner"].id), root_cause="Invented")
    url = f"/api/v1/findings/{f['id']}"
    action = client.post(
        f"{url}/actions", json={"description": "Invented", "owner_id": str(who["doer"].id)}
    ).json()
    return f, f"{url}/actions/{action['id']}"


def upload(client, action_url, content=b"invented proof", name="proof.txt"):
    return client.post(f"{action_url}/files", files={"file": (name, io.BytesIO(content), "text/plain")})


def test_action_owner_attaches_a_file_and_it_counts_as_proof(client, db, seeded):
    f, action_url = setup_action(client, db)
    as_(client, DOER)
    r = upload(client, action_url)
    assert r.status_code == 201, r.text
    files = r.json()["files"]
    assert [(x["filename"], x["size"], x["uploaded_by"]["full_name"]) for x in files] == [
        ("proof.txt", 14, "Dina Doer")
    ]
    download = client.get(f"{action_url}/files/{files[0]['id']}")
    assert download.status_code == 200 and download.content == b"invented proof"
    assert client.patch(action_url, json={"status": "done"}).status_code == 200
    assert client.get(f"/api/v1/findings/{f['id']}").json()["status"] == "awaiting_verification"


def test_others_can_not_attach_files(client, db, seeded):
    _, action_url = setup_action(client, db)
    as_(client, "omar@acme.com")
    assert upload(client, action_url).status_code == 403


def test_uploader_removes_a_file_while_the_action_is_open(client, db, seeded):
    _, action_url = setup_action(client, db)
    as_(client, DOER)
    file_id = upload(client, action_url).json()["files"][0]["id"]
    assert client.delete(f"{action_url}/files/{file_id}").status_code == 204
    assert client.get(f"{action_url}/files/{file_id}").status_code == 404


def test_infected_files_are_refused(client, db, seeded, app, monkeypatch):
    _, action_url = setup_action(client, db)
    app.state.settings.clamav_host = "127.0.0.1"
    monkeypatch.setattr(
        "assayr.findings.files.scan_file", lambda *a, **k: AvResult("infected", signature="Eicar-Test")
    )
    as_(client, DOER)
    r = upload(client, action_url, b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-TEST")
    assert r.status_code == 422 and "Eicar-Test" in r.json()["detail"]
    monkeypatch.setattr("assayr.findings.files.scan_file", lambda *a, **k: AvResult("error", message="down"))
    assert upload(client, action_url).status_code == 503


def test_register_export(client, db, seeded):
    setup_action(client, db)
    r = client.get("/api/v1/findings/export.xlsx")
    assert r.status_code == 200
    book = load_workbook(io.BytesIO(r.content))
    findings = list(book["Findings"].values)
    assert findings[0][:6] == ("Code", "Title", "Grade", "Status", "Framework", "Control")
    assert findings[1][:4] == ("F-001", "A.5.1: Fail", "Major NC", "Action planned")
    actions = list(book["Corrective actions"].values)
    assert actions[1][:4] == ("F-001", 1, "Invented", "Dina Doer")
