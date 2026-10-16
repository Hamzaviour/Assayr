import pytest
from sqlalchemy import select

from assayr.catalogue.models import Requirement
from assayr.nia.importer import parse_nia_pdf
from assayr.nia.seed import seed_nia
from tests.conftest import create_user, sign_in


def make_pdf(lines: list[str]) -> bytes:
    """A minimal one-page PDF with the given text lines (invented test text, never NCSA wording)."""

    def esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    body = "BT /F1 9 Tf 40 800 Td 11 TL " + " ".join(f"({esc(line)}) Tj T*" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(body)} >>\nstream\n{body}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = "%PDF-1.4\n"
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{obj}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n" + "".join(
        f"{o:010d} 00000 n \n" for o in offsets
    )
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


SAMPLE = make_pdf(
    [
        "NATIONAL INFORMATION ASSURANCE STANDARD VERSION 2.1",
        "6. Personnel Security [PS]",
        "PS 1. Example statement one for testing.",
        "PS 2. *Example mandatory statement two.",
        "PS 3. Example statement three.",
    ]
)


def test_parse_finds_version_and_statements():
    parsed = parse_nia_pdf(SAMPLE)
    assert parsed.version == "2.1"
    assert parsed.statements["PS 1"] == "Example statement one for testing."
    assert parsed.statements["PS 2"] == "Example mandatory statement two."


@pytest.fixture
def nia(db, seeded):
    seed_nia(db, seeded)
    db.commit()
    return seeded


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def upload(client, data: bytes):
    return client.post(
        "/api/v1/frameworks/nia-2.1/import", files={"file": ("nia.pdf", data, "application/pdf")}
    )


def test_import_stores_text_for_matched_controls(client, db, nia):
    manager(client, db)
    response = upload(client, SAMPLE)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["matched"] == 3 and body["version"] == "2.1" and "PS 4" in body["unmatched"]
    req = db.scalar(select(Requirement).where(Requirement.ref == "PS 1", Requirement.kind == "control"))
    db.refresh(req)
    assert (
        req.guidance == "Example statement one for testing." and req.attributes["text_source"] == "imported"
    )
    assert client.get("/api/v1/nia/controls/PS 1").json()["text"] == "Example statement one for testing."


def test_wrong_version_is_refused_and_nothing_changes(client, db, nia):
    manager(client, db)
    old = make_pdf(["NATIONAL INFORMATION ASSURANCE STANDARD VERSION 2.0", "PS 1. Old text."])
    response = upload(client, old)
    assert response.status_code == 422 and "version 2.0" in response.json()["detail"]
    assert client.get("/api/v1/nia/controls/PS 1").json()["text"] is None


def test_only_managers_import(client, db, nia):
    create_user(db, "bilal@acme.com", roles=(("control_owner", None),), full_name="Bilal Khan")
    sign_in(client, "bilal@acme.com")
    assert upload(client, SAMPLE).status_code == 403


def test_last_statement_stops_at_the_closing_chapter():
    pdf = make_pdf(
        [
            "NATIONAL INFORMATION ASSURANCE STANDARD VERSION 2.1",
            "VL 8. Example last statement.",
            "6. Compliance and Enforcement 6.1. Compliance and Enforcement Example closing chapter text.",
            "Appendix A Example appendix text.",
        ]
    )
    assert parse_nia_pdf(pdf).statements["VL 8"] == "Example last statement."


def test_a_document_that_is_not_the_nia_standard_is_refused(client, db, nia):
    manager(client, db)
    other = make_pdf(["ACME Travel Policy Version 2.1", "PS 1. Example travel rule."])
    response = upload(client, other)
    assert response.status_code == 422 and "National Information Assurance" in response.json()["detail"]


def test_an_import_that_matches_nothing_is_refused(client, db, nia):
    manager(client, db)
    empty = make_pdf(["NATIONAL INFORMATION ASSURANCE STANDARD VERSION 2.1", "No statements here."])
    response = upload(client, empty)
    assert response.status_code == 422 and "no NIA control statements" in response.json()["detail"]
