import pytest
from sqlalchemy import select

from assayr.audit.models import AuditLog
from tests.conftest import create_user, sign_in

QUESTIONS = {
    "pass_mark": 80,
    "max_attempts": 2,
    "shuffle": False,
    "questions": [
        {
            "kind": "single",
            "text": "Invented single?",
            "options": [{"text": "A", "is_correct": True}, {"text": "B", "is_correct": False}],
        },
        {
            "kind": "multiple",
            "text": "Invented multiple?",
            "options": [
                {"text": "A", "is_correct": True},
                {"text": "B", "is_correct": True},
                {"text": "C", "is_correct": False},
            ],
        },
        {
            "kind": "true_false",
            "text": "Invented statement.",
            "options": [{"text": "True", "is_correct": False}, {"text": "False", "is_correct": True}],
        },
    ],
}


def login(client, email):
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    sign_in(client, email)


@pytest.fixture
def people(db, seeded):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    omar = create_user(db, "omar@acme.com", roles=(("employee", None),), full_name="Omar Ali")
    nadia = create_user(db, "nadia@acme.com", roles=(("employee", None),), full_name="Nadia Noor")
    gone = create_user(db, "gone@acme.com", roles=(("employee", None),), full_name="Gone", active=False)
    omar.department, nadia.department, gone.department = "Finance", "IT", "Finance"
    db.commit()
    return {"omar": omar, "nadia": nadia}


def published(client, assessment=QUESTIONS):
    login(client, "sana@acme.com")
    c = client.post("/api/v1/courses", json={"title": "Security awareness"}).json()
    client.post(
        f"/api/v1/courses/{c['id']}/materials/drive",
        json={"title": "Video", "url": "https://drive.google.com/file/d/1AbC_dEf-123/view"},
    )
    client.post(
        f"/api/v1/courses/{c['id']}/materials/file",
        data={"title": "Handbook"},
        files={"file": ("h.pdf", b"%PDF-1.4 invented", "application/pdf")},
    )
    if assessment:
        client.put(f"/api/v1/courses/{c['id']}/assessment", json=assessment)
    client.post(f"/api/v1/courses/{c['id']}/publish")
    return c


def assign(client, cid, body):
    login(client, "sana@acme.com")
    return client.post(f"/api/v1/courses/{cid}/assign", json=body)


def my_one(client, email):
    login(client, email)
    rows = client.get("/api/v1/my/assignments").json()
    assert len(rows) == 1
    return client.get(f"/api/v1/my/assignments/{rows[0]['id']}").json()


def finish_materials(client, detail):
    for m in detail["materials"]:
        assert (
            client.post(f"/api/v1/my/assignments/{detail['id']}/materials/{m['id']}/done").status_code == 200
        )


def answers(detail, right=True):
    out = {}
    for q in detail["assessment"]["questions"]:
        texts = {
            "Invented single?": ["A"],
            "Invented multiple?": ["A", "B"],
            "Invented statement.": ["False"],
        }[q["text"]]
        if not right and q["kind"] == "multiple":
            texts = ["A"]
        out[q["id"]] = [o["id"] for o in q["options"] if o["text"] in texts]
    return out


def submit(client, detail, body):
    return client.post(f"/api/v1/my/assignments/{detail['id']}/attempts", json={"answers": body})


def test_assign_by_target_without_duplicates(client, db, people):
    c = published(client)
    assert assign(client, c["id"], {"department": "finance"}).json()["created"] == 1
    assert (
        assign(client, c["id"], {"target": "all"}).json()["created"] == 2
    )  # Nadia + Sana; Omar already has it
    assert assign(client, c["id"], {"target": "all"}).json()["created"] == 0
    assert assign(client, c["id"], {"role": "employee"}).json()["created"] == 0
    rules = client.get(f"/api/v1/courses/{c['id']}").json()["rules"]
    assert rules == ["all", "department:finance", "role:employee"]
    rows = client.get(f"/api/v1/courses/{c['id']}/assignments").json()
    assert sorted(r["email"] for r in rows) == ["nadia@acme.com", "omar@acme.com", "sana@acme.com"]


def test_assign_named_people_and_drafts_are_refused(client, db, people):
    login(client, "sana@acme.com")
    draft = client.post("/api/v1/courses", json={"title": "Draft"}).json()
    assert client.post(f"/api/v1/courses/{draft['id']}/assign", json={"target": "all"}).status_code == 409
    c = published(client)
    body = assign(client, c["id"], {"user_ids": [str(people["nadia"].id)], "due_days": 7}).json()
    assert body["created"] == 1
    detail = my_one(client, "nadia@acme.com")
    assert detail["status"] == "assigned" and detail["course_title"] == "Security awareness"


def test_employees_see_only_their_own(client, db, people):
    c = published(client)
    assign(client, c["id"], {"target": "all"})
    omar = my_one(client, "omar@acme.com")
    login(client, "nadia@acme.com")
    assert client.get(f"/api/v1/my/assignments/{omar['id']}").status_code == 404
    assert client.get("/api/v1/courses").status_code == 403
    assert client.get(f"/api/v1/courses/{c['id']}/assignments").status_code == 403


def test_the_assessment_never_reveals_answers_and_waits_for_the_materials(client, db, people):
    c = published(client)
    assign(client, c["id"], {"target": "all"})
    detail = my_one(client, "omar@acme.com")
    assert all("is_correct" not in o for q in detail["assessment"]["questions"] for o in q["options"])
    assert detail["assessment_locked"] is True
    early = submit(client, detail, answers(detail))
    assert early.status_code == 409 and "materials" in early.json()["detail"]
    file_material = next(m for m in detail["materials"] if m["kind"] == "file")
    got = client.get(f"/api/v1/my/assignments/{detail['id']}/materials/{file_material['id']}/file")
    assert got.status_code == 200 and got.content == b"%PDF-1.4 invented"


def test_passing(client, db, people):
    c = published(client)
    assign(client, c["id"], {"target": "all"})
    detail = my_one(client, "omar@acme.com")
    finish_materials(client, detail)
    result = submit(client, detail, answers(detail)).json()
    assert result == {"score": 100.0, "passed": True, "wrong": [], "attempts_left": 1}
    again = client.get(f"/api/v1/my/assignments/{detail['id']}").json()
    assert again["status"] == "passed" and again["completed_at"]
    assert submit(client, detail, answers(detail)).status_code == 409


def test_marking_is_exact_and_foreign_answers_do_not_count(client, db, people):
    c = published(client)
    assign(client, c["id"], {"target": "all"})
    detail = my_one(client, "omar@acme.com")
    finish_materials(client, detail)
    body = answers(detail, right=False)
    single = next(q for q in detail["assessment"]["questions"] if q["kind"] == "single")
    tf = next(q for q in detail["assessment"]["questions"] if q["kind"] == "true_false")
    body[single["id"]] = body[single["id"]] + [tf["options"][1]["id"]]  # an option from another question
    body["not-a-question"] = ["x"]
    result = submit(client, detail, body).json()
    multiple = next(q for q in detail["assessment"]["questions"] if q["kind"] == "multiple")
    assert result["passed"] is False and result["score"] == pytest.approx(66.7, abs=0.1)
    assert result["wrong"] == [multiple["id"]] and result["attempts_left"] == 1


def test_running_out_of_attempts_and_extra_attempts(client, db, people):
    c = published(client)
    assign(client, c["id"], {"target": "all"})
    detail = my_one(client, "omar@acme.com")
    finish_materials(client, detail)
    submit(client, detail, answers(detail, right=False))
    last = submit(client, detail, answers(detail, right=False)).json()
    assert last["attempts_left"] == 0 and last["passed"] is False
    assert client.get(f"/api/v1/my/assignments/{detail['id']}").json()["status"] == "failed"
    blocked = submit(client, detail, answers(detail))
    assert blocked.status_code == 409 and "attempts" in blocked.json()["detail"]
    login(client, "sana@acme.com")
    url = f"/api/v1/assignments/{detail['id']}/attempts"
    assert client.post(url, json={"extra": 1}).status_code == 422
    assert client.post(url, json={"extra": 1, "reason": "Retraining done"}).status_code == 200
    assert (
        db.scalar(select(AuditLog).where(AuditLog.action == "assignment.attempts")).reason
        == "Retraining done"
    )
    login(client, "omar@acme.com")
    assert submit(client, detail, answers(detail)).json()["passed"] is True


def test_a_course_without_an_assessment_passes_when_the_materials_are_done(client, db, people):
    c = published(client, assessment=None)
    assign(client, c["id"], {"target": "all"})
    detail = my_one(client, "omar@acme.com")
    finish_materials(client, detail)
    assert client.get(f"/api/v1/my/assignments/{detail['id']}").json()["status"] == "passed"


def test_overdue_is_derived(client, db, people, clock):
    c = published(client)
    assign(client, c["id"], {"target": "all", "due_days": 3})
    clock.advance(days=4)
    login(client, "omar@acme.com")
    rows = client.get("/api/v1/my/assignments").json()
    assert rows[0]["overdue"] is True
    login(client, "sana@acme.com")
    assert client.get(f"/api/v1/courses/{c['id']}").json()["counts"]["overdue"] == 3
