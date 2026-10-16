import uuid
from datetime import date

import pytest

from assayr.db import utcnow
from assayr.training.drive import drive_file_id
from assayr.training.models import Assignment
from tests.conftest import create_user, sign_in

DRIVE = "https://drive.google.com/file/d/1AbC_dEf-123/view?usp=sharing"


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def course(client, **extra):
    response = client.post("/api/v1/courses", json={"title": "Security awareness 2026", **extra})
    assert response.status_code == 201, response.text
    return response.json()


def add_drive(client, cid, url=DRIVE, title="Phishing video"):
    return client.post(f"/api/v1/courses/{cid}/materials/drive", json={"title": title, "url": url})


def add_file(client, cid, data=b"%PDF-1.4 invented handbook", name="handbook.pdf", title="Handbook"):
    return client.post(
        f"/api/v1/courses/{cid}/materials/file",
        data={"title": title},
        files={"file": (name, data, "application/pdf")},
    )


QUESTIONS = {
    "pass_mark": 80,
    "max_attempts": 3,
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


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (DRIVE, "1AbC_dEf-123"),
        ("https://drive.google.com/open?id=1AbC_dEf-123", "1AbC_dEf-123"),
        ("https://drive.google.com/file/d/1AbC_dEf-123/preview", "1AbC_dEf-123"),
    ],
)
def test_drive_links_are_reduced_to_the_file_id(url, expected):
    assert drive_file_id(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/file/d/1AbC/view",
        "http://drive.google.com/file/d/1AbC/view",
        "javascript:alert(1)",
        "https://drive.google.com/drive/folders/x",
    ],
)
def test_other_links_are_refused(url):
    with pytest.raises(ValueError):
        drive_file_id(url)


def test_create_and_list_courses(client, db, seeded):
    manager(client, db)
    c = course(client)
    assert c["status"] == "draft" and c["recurrence_months"] == 12 and c["due_days"] == 30
    assert [r["title"] for r in client.get("/api/v1/courses").json()] == ["Security awareness 2026"]
    one_off = course(client, title="Induction", recurrence_months=None)
    assert one_off["recurrence_months"] is None


def test_materials_drive_and_file(client, db, seeded):
    manager(client, db)
    c = course(client)
    drive = add_drive(client, c["id"]).json()
    assert drive["kind"] == "drive" and drive["drive_file_id"] == "1AbC_dEf-123"
    assert add_drive(client, c["id"], url="https://evil.example/x").status_code == 422
    pdf = add_file(client, c["id"]).json()
    assert pdf["kind"] == "file" and pdf["mime"] == "application/pdf"
    assert add_file(client, c["id"], data=b"MZ\x90\x00binary", name="setup.exe").status_code == 422
    detail = client.get(f"/api/v1/courses/{c['id']}").json()
    assert [m["title"] for m in detail["materials"]] == ["Phishing video", "Handbook"]


def test_video_files_stream_with_ranges(client, db, seeded):
    manager(client, db)
    c = course(client)
    video = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
    m = add_file(client, c["id"], data=video, name="intro.mp4", title="Intro").json()
    assert m["mime"] == "video/mp4"
    url = f"/api/v1/courses/{c['id']}/materials/{m['id']}/file"
    whole = client.get(url)
    assert (
        whole.status_code == 200
        and whole.content == video
        and whole.headers["x-content-type-options"] == "nosniff"
    )
    part = client.get(url, headers={"Range": "bytes=0-3"})
    assert part.status_code == 206 and part.content == video[:4]


def test_upload_limit(client, db, seeded, app):
    app.state.settings.training_upload_mb = 1
    manager(client, db)
    c = course(client)
    big = b"%PDF-1.4" + b"x" * (1024 * 1024)
    assert add_file(client, c["id"], data=big).status_code == 413


def test_assessment_validation(client, db, seeded):
    manager(client, db)
    c = course(client)
    url = f"/api/v1/courses/{c['id']}/assessment"
    saved = client.put(url, json=QUESTIONS)
    assert saved.status_code == 200, saved.text
    assert [q["kind"] for q in saved.json()["questions"]] == ["single", "multiple", "true_false"]
    bad_single = {
        **QUESTIONS,
        "questions": [
            {
                "kind": "single",
                "text": "x",
                "options": [{"text": "A", "is_correct": True}, {"text": "B", "is_correct": True}],
            }
        ],
    }
    assert client.put(url, json=bad_single).status_code == 422
    none_correct = {
        **QUESTIONS,
        "questions": [
            {
                "kind": "multiple",
                "text": "x",
                "options": [{"text": "A", "is_correct": False}, {"text": "B", "is_correct": False}],
            }
        ],
    }
    assert client.put(url, json=none_correct).status_code == 422
    one_option = {
        **QUESTIONS,
        "questions": [{"kind": "single", "text": "x", "options": [{"text": "A", "is_correct": True}]}],
    }
    assert client.put(url, json=one_option).status_code == 422
    bad_tf = {
        **QUESTIONS,
        "questions": [
            {
                "kind": "true_false",
                "text": "x",
                "options": [{"text": "Yes", "is_correct": True}, {"text": "No", "is_correct": False}],
            }
        ],
    }
    assert client.put(url, json=bad_tf).status_code == 422
    assert client.put(url, json={**QUESTIONS, "pass_mark": 120}).status_code == 422


def test_publish_needs_a_material_and_archive(client, db, seeded):
    manager(client, db)
    c = course(client)
    assert client.post(f"/api/v1/courses/{c['id']}/publish").status_code == 409
    add_drive(client, c["id"])
    assert client.post(f"/api/v1/courses/{c['id']}/publish").json()["status"] == "published"
    assert client.post(f"/api/v1/courses/{c['id']}/archive").json()["status"] == "archived"


def test_courses_with_assignments_keep_their_content(client, db, seeded):
    manager(client, db)
    c = course(client)
    m = add_drive(client, c["id"]).json()
    client.put(f"/api/v1/courses/{c['id']}/assessment", json=QUESTIONS)
    client.post(f"/api/v1/courses/{c['id']}/publish")
    omar = create_user(db, "omar@acme.com", roles=(("employee", None),), full_name="Omar")
    db.add(
        Assignment(
            course_id=uuid.UUID(c["id"]),
            user_id=omar.id,
            source="user",
            assigned_at=utcnow(),
            due_at=date(2030, 1, 1),
        )
    )
    db.commit()
    assert client.delete(f"/api/v1/courses/{c['id']}/materials/{m['id']}").status_code == 409
    assert client.put(f"/api/v1/courses/{c['id']}/assessment", json=QUESTIONS).status_code == 409
    assert add_drive(client, c["id"], title="Extra").status_code == 201


@pytest.mark.parametrize("role", ["viewer", "employee", "control_owner"])
def test_only_training_managers_manage_courses(client, db, seeded, role):
    create_user(db, "x@acme.com", roles=((role, None),), full_name="X")
    sign_in(client, "x@acme.com")
    assert client.get("/api/v1/courses").status_code == 403
    assert client.post("/api/v1/courses", json={"title": "x"}).status_code == 403
