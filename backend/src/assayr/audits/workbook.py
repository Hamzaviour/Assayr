"""The internal audit workbook ("NIA - IA report" layout): export an audit, read an existing workbook."""

import io
import zipfile
from dataclasses import dataclass

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

from assayr.audits.models import Audit
from assayr.exports import safe_cell

MAX_ROWS = 2000
MAX_REF_LENGTH = 20
_RESULTS = {"pass": "pass", "fail": "fail", "partial": "partial", "na": "na", "n/a": "na"}
_TEST_TYPES = {"da": "DA", "oea": "OEA", "both": "Both"}
_RESULT_LABEL = {"pass": "Pass", "fail": "Fail", "partial": "Partial", "na": "NA"}


class WorkbookError(Exception):
    pass


@dataclass
class ImportRow:
    ref: str
    domain: str | None
    sub_domain: str | None
    assessment_area: str | None
    test_type: str | None
    requirement: str | None
    result: str | None


def headers(framework: str) -> list[str]:
    return [
        "Sr. No.",
        "Domain Name",
        "Sub Domain Name",
        "NIA Control" if framework == "nia-2.1" else "ISO Control",
        "Control Description/Assessment Area",
        "Design Assessment (DA) / Operating Effectiveness Assessment (OEA) / Both",
        "Mandatory (M) / Additional (A)",
        "Control status (Pass/Fail/Partial)",
    ]


def sheet_title(framework: str) -> str:
    return "NIA - IA report" if framework == "nia-2.1" else "ISO - IA report"


def export_workbook(audit: Audit) -> Workbook:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_title(audit.framework)
    sheet.append(headers(audit.framework))
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for number, item in enumerate(audit.items, start=1):
        sheet.append(
            [
                number,
                safe_cell(item.domain),
                safe_cell(item.sub_domain),
                item.ref,
                safe_cell(item.assessment_area),
                item.test_type,
                item.requirement,
                _RESULT_LABEL.get(item.result or ""),
            ]
        )
    sheet.freeze_panes = "A2"
    return workbook


def _norm(value) -> str:
    return " ".join(str(value).split()).lower() if value is not None else ""


def _column(header: list[str], test) -> int | None:
    return next((i for i, h in enumerate(header) if test(h)), None)


def _text(row: tuple, index: int | None) -> str | None:
    if index is None or index >= len(row) or row[index] is None:
        return None
    text = " ".join(str(row[index]).split())
    return text or None


def read_workbook(data: bytes) -> list[ImportRow]:
    """Reads the first sheet; columns are found by their header text, whatever the spacing or case."""
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (zipfile.BadZipFile, OSError, KeyError, ValueError) as exc:
        raise WorkbookError("This file is not an Excel workbook (.xlsx).") from exc
    rows = list(workbook.worksheets[0].iter_rows(values_only=True))
    workbook.close()
    start = next(
        (i for i, row in enumerate(rows[:20]) if any(_norm(v).startswith("control status") for v in row)),
        None,
    )
    if start is None:
        raise WorkbookError('The workbook has no "Control status (Pass/Fail/Partial)" column.')
    header = [_norm(v) for v in rows[start]]
    ref_col = _column(header, lambda h: h in ("nia control", "iso control") or h.endswith(" control"))
    if ref_col is None:
        raise WorkbookError('The workbook has no "NIA Control" column.')
    cols = {
        "domain": _column(header, lambda h: h.startswith("domain")),
        "sub_domain": _column(header, lambda h: h.startswith("sub domain") or h.startswith("subdomain")),
        "area": _column(header, lambda h: h.startswith("control description") or "assessment area" in h),
        "test": _column(header, lambda h: h.startswith("design assessment")),
        "requirement": _column(header, lambda h: h.startswith("mandatory")),
        "result": _column(header, lambda h: h.startswith("control status")),
    }
    # A control reference is short; longer text in that column is a note (e.g. a closing paragraph).
    body = [
        row for row in rows[start + 1 :] if _text(row, ref_col) and len(_text(row, ref_col)) <= MAX_REF_LENGTH
    ]
    if len(body) > MAX_ROWS:
        raise WorkbookError(f"The workbook has more than {MAX_ROWS} controls.")
    out = []
    for row in body:
        requirement = (_text(row, cols["requirement"]) or "").upper()[:1]
        out.append(
            ImportRow(
                ref=_text(row, ref_col),
                domain=_text(row, cols["domain"]),
                sub_domain=_text(row, cols["sub_domain"]),
                assessment_area=_text(row, cols["area"]),
                test_type=_TEST_TYPES.get((_text(row, cols["test"]) or "").lower()),
                requirement=requirement if requirement in ("M", "A") else None,
                result=_RESULTS.get((_text(row, cols["result"]) or "").lower()),
            )
        )
    return out
