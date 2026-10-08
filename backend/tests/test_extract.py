import pytest

from assayr.evidence.extract import DOCX, PDF, XLSX, extract, sniff
from tests.fixtures import PNG_BYTES, make_docx, make_pdf, make_xlsx


def write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return path


@pytest.mark.parametrize(
    "head,name,expected",
    [
        (b"%PDF-1.4 rest", "policy.pdf", PDF),
        (b"%PDF-1.4 rest", "renamed.txt", PDF),
        (PNG_BYTES[:16], "shot.png", "image/png"),
        (b"\xff\xd8\xff\xe0\x00\x10JFIF", "photo.jpg", "image/jpeg"),
        (b"PK\x03\x04rest", "review.xlsx", XLSX),
        (b"PK\x03\x04rest", "policy.docx", DOCX),
        (b"PK\x03\x04rest", "archive.zip", None),
        (b"MZ\x90\x00\x03\x00", "invoice.pdf", None),
        (b"<html><script>alert(1)</script>", "page.html", None),
        (b"<html><script>alert(1)</script>", "notes.txt", None),
        (b"Access review\ncompleted", "notes.txt", "text/plain"),
        (b"user,approved\nsana,yes", "export.csv", "text/csv"),
        (b'{"mfa": true}', "config.json", "application/json"),
    ],
)
def test_sniff(head, name, expected):
    assert sniff(head, name) == expected


def test_pdf_text_and_page_count(tmp_path):
    path = write(tmp_path, "p.pdf", make_pdf(["Acme Financial Services", "Approved by: Tariq Qureshi"]))
    result = extract(path, PDF)
    assert result.error is None and result.pages == 1
    assert "Approved by: Tariq Qureshi" in result.text


def test_docx_text_tables_and_author(tmp_path):
    data = make_docx(
        ["Backup policy"], table=[["Version", "Approved by"], ["3.0", "Tariq Qureshi"]], author="Sana"
    )
    result = extract(write(tmp_path, "b.docx", data), DOCX)
    assert "Backup policy" in result.text and "Tariq Qureshi" in result.text
    assert result.metadata["author"] == "Sana"


def test_xlsx_cell_values(tmp_path):
    result = extract(write(tmp_path, "r.xlsx", make_xlsx([["User", "Reviewed"], ["sana", "yes"]])), XLSX)
    assert "sana | yes" in result.text


def test_corrupt_pdf_is_reported_unreadable(tmp_path):
    result = extract(write(tmp_path, "bad.pdf", b"%PDF-1.4\nnot really a pdf"), PDF)
    assert result.error == "The file could not be read."


def test_text_file_is_read(tmp_path):
    assert extract(write(tmp_path, "n.txt", "Résumé ok".encode()), "text/plain").text == "Résumé ok"


def test_images_have_no_text_yet(tmp_path):
    result = extract(write(tmp_path, "s.png", PNG_BYTES), "image/png")
    assert result.text == "" and result.error is None


def test_unsupported_type_is_an_error(tmp_path):
    assert (
        extract(write(tmp_path, "x.bin", b"\x00\x01"), None).error
        == "This file type isn't accepted as evidence."
    )
