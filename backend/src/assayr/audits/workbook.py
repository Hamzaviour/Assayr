"""The internal audit workbook ("NIA - IA report" layout): export an audit, read an existing workbook."""

import io
from dataclasses import dataclass

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

from assayr.audits.models import Audit
from assayr.exports import safe_cell

MAX_ROWS = 2000
MAX_REF_LENGTH = 20
HEADER_SEARCH_ROWS = 20
MAX_EMPTY_RUN = 500
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
        {"nia-2.1": "NIA Control", "iso42001": "ISO 42001 Control"}.get(framework, "ISO Control"),
        "Control Description/Assessment Area",
        "Design Assessment (DA) / Operating Effectiveness Assessment (OEA) / Both",
        "Mandatory (M) / Additional (A)",
        "Control status (Pass/Fail/Partial)",
    ]


def sheet_title(framework: str) -> str:
    return {"nia-2.1": "NIA - IA report", "iso42001": "ISO 42001 - IA report"}.get(
        framework, "ISO - IA report"
    )


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


def read_workbook(data: bytes) -> tuple[list[ImportRow], list[str]]:
    """Reads the first sheet; columns are found by their header text, whatever the spacing or case.

    Returns the control rows and a note for each row that had content but no usable control reference.
    """
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # any malformed archive or XML is the user's file, not our error
        raise WorkbookError("This file is not an Excel workbook (.xlsx).") from exc
    try:
        return _read_rows(workbook.worksheets[0].iter_rows(values_only=True))
    except WorkbookError:
        raise
    except Exception as exc:
        raise WorkbookError("This workbook could not be read. Save it again from Excel and retry.") from exc
    finally:
        workbook.close()


def _read_rows(rows) -> tuple[list[ImportRow], list[str]]:
    header = None
    for number, row in enumerate(rows, start=1):
        if any(_norm(v).startswith("control status") for v in row):
            header = [_norm(v) for v in row]
            header_row = number
            break
        if number >= HEADER_SEARCH_ROWS:
            break
    if header is None:
        raise WorkbookError('The workbook has no "Control status (Pass/Fail/Partial)" column.')
    ref_col = _column(header, lambda h: h in ("nia control", "iso control") or h.endswith(" control"))
    if ref_col is None:
        raise WorkbookError('The workbook has no "NIA Control" column.')
    cols = {
        "number": _column(header, lambda h: h.startswith("sr")),
        "domain": _column(header, lambda h: h.startswith("domain")),
        "sub_domain": _column(header, lambda h: h.startswith("sub domain") or h.startswith("subdomain")),
        "area": _column(header, lambda h: h.startswith("control description") or "assessment area" in h),
        "test": _column(header, lambda h: h.startswith("design assessment")),
        "requirement": _column(header, lambda h: h.startswith("mandatory")),
        "result": _column(header, lambda h: h.startswith("control status")),
    }
    out: list[ImportRow] = []
    skipped: list[str] = []
    empty_run = 0
    for row_number, row in enumerate(rows, start=header_row + 1):
        if not any(_text(row, i) for i in range(len(row))):
            empty_run += 1
            if empty_run >= MAX_EMPTY_RUN:
                break  # the rest of the sheet is blank formatting, not data
            continue
        empty_run = 0
        ref = _text(row, ref_col)
        if not ref or len(ref) > MAX_REF_LENGTH:
            # A note row (no number, no result) is skipped quietly; a control row without a reference is reported.
            if _text(row, cols["number"]) or _text(row, cols["result"]):
                skipped.append(f"Row {row_number}: no control reference")
            continue
        if len(out) >= MAX_ROWS:
            raise WorkbookError(f"The workbook has more than {MAX_ROWS} controls.")
        requirement = (_text(row, cols["requirement"]) or "").upper()[:1]
        out.append(
            ImportRow(
                ref=ref,
                domain=_text(row, cols["domain"]),
                sub_domain=_text(row, cols["sub_domain"]),
                assessment_area=_text(row, cols["area"]),
                test_type=_TEST_TYPES.get((_text(row, cols["test"]) or "").lower()),
                requirement=requirement if requirement in ("M", "A") else None,
                result=_RESULTS.get((_text(row, cols["result"]) or "").lower()),
            )
        )
    return out, skipped
