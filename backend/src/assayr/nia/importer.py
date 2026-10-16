"""Import the official NIA control text from the customer's own copy of the NCSA standard.

The text is stored in this installation only (Requirement.guidance); Assayr never ships it.
"""

import re
from dataclasses import dataclass, field

import pypdfium2 as pdfium
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.catalogue.models import Requirement
from assayr.nia.service import framework

EXPECTED_VERSION = "2.1"
_VERSION = re.compile(r"VERSION\s+(\d+\.\d+)|\bV\s?(\d+\.\d+)\b", re.IGNORECASE)
# "XX n. statement" (or "XXn." written inline); a leading "*" marks a mandatory control.
_STATEMENT = re.compile(r"(?:^|\s)([A-Z]{2}) ?(\d{1,3})\.\s+\*?(?=[A-Z\"(“])")
# Text that is not part of a statement: running page headers and the next section's heading.
_HEADER = re.compile(
    r"National Information Assurance Standard\s*-\s*V\d+\.\d+\s*VERSION \d+\.\d+", re.IGNORECASE
)
_SECTION = re.compile(
    r"\s\d+(?:\.\d+)?\.?\s+(?:[A-Z][A-Za-z&/,\- ]+\[[A-Z]{2}\]|Control Statements|Objectives)\b"
    # A top-level chapter followed by its first subsection, e.g. "6. Compliance and Enforcement 6.1. ...".
    r"|\s(\d+)\.\s+[A-Z][A-Za-z&/,\- ]{2,60}?\s\1\.1\.\s"
)


class NiaImportError(Exception):
    pass


@dataclass
class ParsedNia:
    version: str | None
    is_nia: bool = True
    statements: dict[str, str] = field(default_factory=dict)


@dataclass
class ImportResult:
    version: str
    matched: int
    unmatched: list[str]


def _text(data: bytes) -> str:
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        raise NiaImportError("This file is not a readable PDF.") from exc
    pages = [pdf[i].get_textpage().get_text_range() for i in range(len(pdf))]
    return " ".join(" ".join(pages).replace("￾", "'").replace("�", "'").split())


def parse_nia_pdf(data: bytes) -> ParsedNia:
    text = _text(data)
    head = text[:4000]
    match = _VERSION.search(head)
    version = next((g for g in match.groups() if g), None) if match else None
    text = _HEADER.sub(" ", text)
    hits = list(_STATEMENT.finditer(text))
    statements: dict[str, str] = {}
    for i, m in enumerate(hits):
        ref = f"{m.group(1)} {int(m.group(2))}"
        if ref in statements:
            continue
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        body = text[m.end() : end]
        section = _SECTION.search(body)
        if section:
            body = body[: section.start()]
        statements[ref] = " ".join(body.split()).strip()
    is_nia = "NATIONAL INFORMATION ASSURANCE" in head.upper()
    return ParsedNia(version=version, statements=statements, is_nia=is_nia)


def apply_import(db: Session, parsed: ParsedNia) -> ImportResult:
    if not parsed.is_nia:
        raise NiaImportError(
            "This document is not the National Information Assurance standard. Choose your copy of the NCSA PDF."
        )
    if parsed.version != EXPECTED_VERSION:
        found = f"version {parsed.version}" if parsed.version else "no version number"
        raise NiaImportError(f"This document shows {found}; Assayr expects NIA version {EXPECTED_VERSION}.")
    fw = framework(db)
    if fw is None:
        raise NiaImportError("NIA is not set up in this installation yet. Run assayr seed first.")
    controls = db.scalars(
        select(Requirement).where(Requirement.framework_id == fw.id, Requirement.kind == "control")
    )
    controls = list(controls)
    if not any(parsed.statements.get(req.ref) for req in controls):
        raise NiaImportError(
            "This document has no NIA control statements Assayr recognises; nothing was changed."
        )
    matched, unmatched = 0, []
    for req in controls:
        statement = parsed.statements.get(req.ref)
        if statement:
            req.guidance = statement
            req.attributes = {**(req.attributes or {}), "text_source": "imported"}
            matched += 1
        else:
            unmatched.append(req.ref)
    return ImportResult(version=parsed.version, matched=matched, unmatched=unmatched)
